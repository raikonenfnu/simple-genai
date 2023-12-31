import torch
from transformers import CLIPTextModel, CLIPTokenizer
from diffusers import AutoencoderKL, UNet2DConditionModel, LMSDiscreteScheduler
from tqdm.auto import tqdm
from PIL import Image

if __name__ == "__main__":
    # SD1: "CompVis/stable-diffusion-v1-4"
    # SD2: "stabilityai/stable-diffusion-2-1"
    # 1. Load the autoencoder model which will be used to decode the latents into image space.
    vae = AutoencoderKL.from_pretrained("CompVis/stable-diffusion-v1-4", subfolder="vae")

    # 2. Load the tokenizer and text encoder to tokenize and encode the text.
    tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-large-patch14")
    text_encoder = CLIPTextModel.from_pretrained("openai/clip-vit-large-patch14")

    # 3. The UNet model for generating the latents.
    unet = UNet2DConditionModel.from_pretrained("CompVis/stable-diffusion-v1-4", subfolder="unet")
    scheduler = LMSDiscreteScheduler(beta_start=0.00085, beta_end=0.012, beta_schedule="scaled_linear", num_train_timesteps=1000)

    # Check and assign devices.
    if torch.cuda.is_available():
        torch_device = "cuda"
    elif torch.backends.mps.is_available():
        torch_device = "mps"
    else:
        print("Cannot find GPUs, defaulting to use CPU.")
        torch_device = "cpu"
    vae.to(torch_device)
    text_encoder.to(torch_device)
    unet.to(torch_device)

    # Setup image options.
    prompt = ["a photograph of an astronaut riding a horse"]
    height = 512                        # default height of Stable Diffusion
    width = 512                         # default width of Stable Diffusion
    num_inference_steps = 100           # Number of denoising steps
    guidance_scale = 7.5                # Scale for classifier-free guidance
    generator = torch.manual_seed(1024)    # Seed generator to create the inital latent noise
    batch_size = len(prompt)

    # Conditional text embeddings from prompt, this will be used to condition
    # the UNet model and guide the image generation.
    text_input = tokenizer(prompt, padding="max_length", max_length=tokenizer.model_max_length, truncation=True, return_tensors="pt")
    text_embeddings = text_encoder(text_input.input_ids.to(torch_device))[0]

    # Unconditional text embeddings for classifier-free guidance,
    # which are just the embeddings for the padding token (empty text).
    max_length = text_input.input_ids.shape[-1]
    uncond_input = tokenizer(
        [""] * batch_size, padding="max_length", max_length=max_length, return_tensors="pt"
    )
    uncond_embeddings = text_encoder(uncond_input.input_ids.to(torch_device))[0]

    # For classifier-free guidance, we need to do two forward passes:
    # one with the conditioned input (text_embeddings),
    # and another with the unconditional embeddings (uncond_embeddings).
    # In practice, we can concatenate both into a single batch to avoid doing two forward passes.
    text_embeddings = torch.cat([uncond_embeddings, text_embeddings])

    # Initial random noises.
    latents = torch.randn(
        (batch_size, unet.in_channels, height // 8, width // 8),
        generator=generator,
    )
    # The latents at this stage we'll see their shape is torch.Size([1, 4, 64, 64]),
    # much smaller than the image we want to generate.
    # The model will transform this latent representation (pure noise) into a 512 × 512 image later on.
    latents = latents.to(torch_device)

    # We initialize the scheduler with our chosen num_inference_steps.
    # This will compute the sigmas and exact time step values to be used during the denoising process.
    scheduler.set_timesteps(num_inference_steps)

    # The K-LMS scheduler needs to multiply the latents by its sigma values.
    latents = latents * scheduler.init_noise_sigma

    # Denoising loop:
    for t in tqdm(scheduler.timesteps):
        # expand the latents if we are doing classifier-free guidance to avoid doing two forward passes.
        latent_model_input = torch.cat([latents] * 2)

        latent_model_input = scheduler.scale_model_input(latent_model_input, timestep=t)

        # predict the noise residual
        with torch.no_grad():
            noise_pred = unet(latent_model_input, t, encoder_hidden_states=text_embeddings).sample

        # perform guidance
        noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
        noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)

        # compute the previous noisy sample x_t -> x_t-1
        latents = scheduler.step(noise_pred, t, latents).prev_sample

    # Use the vae to decode the generated latents back into the image.
    # scale and decode the image latents with vae
    latents = 1 / 0.18215 * latents
    with torch.no_grad():
        image = vae.decode(latents).sample

    # Saving image generated.
    image = (image / 2 + 0.5).clamp(0, 1)
    image = image.detach().cpu().permute(0, 2, 3, 1).numpy()
    images = (image * 255).round().astype("uint8")
    pil_images = [Image.fromarray(image) for image in images]
    filename = prompt[0].replace(" ","_")
    pil_images[0].save(f"{filename}.jpeg")























