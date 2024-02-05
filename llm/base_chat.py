import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import argparse
from simple_llm import SimpleLLM

DEFAULT_HF_MODEL_NAME = "meta-llama/Llama-2-7b-chat-hf"
B_INST, E_INST = "[INST]", "[/INST]"
B_SYS, E_SYS = "<s>", "</s>"
DEFAULT_CHAT_SYS_PROMPT = """<s>[INST] <<SYS>>
Be concise. You are a helpful, respectful and honest assistant. If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.\n <</SYS>>\n\n
"""
MAX_NUM_TOKENS=1028

parser = argparse.ArgumentParser()
parser.add_argument(
    "--hf_auth_token",
    type=str,
    default="",
    help="The Hugging face auth token, required for some models",
)
parser.add_argument(
    "--hf_model_name",
    type=str,
    help="HF model name",
    default="meta-llama/Llama-2-7b-chat-hf",
)
parser.add_argument(
    "--max_num_tokens",
    type=int,
    default=1024,
    help="Max number of tokens generated per prompt",
)
parser.add_argument(
    "--device",
    type=str,
    help="Device to run models on.",
    default="cpu",
)

def append_user_prompt(history, input_prompt):
    user_prompt = f"{B_INST} {input_prompt} {E_INST}"
    history += user_prompt
    return history

def append_bot_prompt(history, input_prompt):
    user_prompt = f"{B_SYS} {input_prompt}{E_SYS} {E_SYS}"
    history += user_prompt
    return history

def chat(hf_model_name,
         hf_auth_token,
         max_num_tokens,
         device):
    tokenizer = AutoTokenizer.from_pretrained(
        hf_model_name,
        use_fast=False,
        token=hf_auth_token,
    )
    llm = SimpleLLM(hf_model_name,
                    hf_auth_token,
                    tokenizer.eos_token_id,
                    device=device,
                    max_num_tokens=max_num_tokens)
    prompt = DEFAULT_CHAT_SYS_PROMPT
    while True:
        user_prompt = input("User prompt: ")
        prompt = append_user_prompt(prompt, user_prompt)
        initial_input = tokenizer(prompt, return_tensors="pt")
        example_input_id = initial_input.input_ids
        result = llm.generate(example_input_id)
        bot_response = tokenizer.decode(result, skip_special_tokens=True)
        print(f"\nBOT: {bot_response}\n")
        prompt = append_bot_prompt(prompt, bot_response)

if __name__ == "__main__":
    args = parser.parse_args()
    chat(args.hf_model_name, args.hf_auth_token, args.max_num_tokens, args.device)
