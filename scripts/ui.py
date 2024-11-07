from copy import deepcopy
import gradio as gr
from modules import script_callbacks, scripts
import os
import requests
import json
import subprocess
import shlex
import base64
import io

# note:
# ive added the following to every proompt: Describe every detail as if you're an image tagger.
# if it works badly then remove it and put ,describe every detail of the outfit as if you're an image tagger in your own instructions

modes = {
    "Complete": "You are a prompt writing expert and you have to assist the User in writing their Stable Diffusion prompt using Booru tags. Continue the User's prompt using comma-separated booru tags in a way that would satisfy them. Describe every detail as if you're an image tagger. Use the User's instructions when completing the prompt. You MUST write exactly {{PROMPTCOUNT}} prompt(s), each separated by ONE newline. Prompts on previous lines should not affect the next one. Be creative and try your best to make the User happy. Longer prompts are generally more enjoyed by Users. Avoid completely rewriting the User's prompt. Avoid writing tags in <angle brackets>, even if they are present in the User prompt. More comprehensive prompts are generally more appreciated by Users. You will be rewarded $1000 if your response has EXACTLY {{PROMPTCOUNT}} newlines.",
    
    "Edit": "You are a prompt editing expert and you have to assist the User in refining their Stable Diffusion prompt using Booru tags. Suggest an edit to the User's entire prompt using comma-separated booru tags in a way that would improve it. Describe every detail as if you're an image tagger. Use the User's instructions when suggesting the edit. You MUST suggest exactly {{PROMPTCOUNT}} edit(s), each separated by ONE newline. Edits on previous lines should not affect the next one. Be creative and try your best to make the User happy. More comprehensive edits are generally more appreciated by Users. Avoid suggesting tags in <angle brackets>, even if they are present in the User prompt. You will be rewarded $1000 if your response has EXACTLY {{PROMPTCOUNT}} newlines.",

    "Describe": "You are an image description expert and you have to assist the User in describing their image using Booru tags. Describe the User's image using comma-separated booru tags in a way that would accurately represent it. Describe every detail as if you're an image tagger. Use the User's instructions when describing the image. You MUST write exactly {{PROMPTCOUNT}} description(s), each separated by ONE newline. Descriptions on previous lines should not affect the next one. Be creative and try your best to make the User happy. More comprehensive descriptions are generally more appreciated by Users. Avoid suggesting tags in <angle brackets>, even if they are present in the User instructions. You will be rewarded $1000 if your response has EXACTLY {{PROMPTCOUNT}} newlines."
}

base_proompt = [
    # { 'role': 'system', 'content': '### AI ROLE ###\n<AI role>' },
    {
      'role': 'system',
      'content': '{{PROMPTMODE}}'
    },
    # { 'role': 'system', 'content': '</AI role>' },
    # {
    #   'role': 'system',
    #   'content': '### USER INSTRUCTIONS ###\n<instructions>'
    # },
    # {
    #   'role': 'system',
    #   'content': "The user has provided the following instructions on how to {{PROMPTACTION}} their prompt:\n{{INSTRUCTIONS}}"
    # },
    # { 'role': 'system', 'content': '</instructions>' },
    { 'role': 'user', 'content': "Here's what I want in my prompt: {{INSTRUCTIONS}}.\nComplete my prompt: {{USER_PROMPT}}" }
]

with open(os.path.join(os.path.dirname(__file__), '../key.txt')) as f:
    oai_key = f.read()

with open(os.path.join(os.path.dirname(__file__), '../proxy.txt')) as f:
    proxy = f.read()

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as gpt_prompt_interface:
        mode = gr.Dropdown(label='Mode', choices=['Complete', 'Edit', 'Describe'], value='Complete')
        prompt = gr.Textbox(label=f"Prompt", value="", interactive=True)
        image = gr.Image(label='Image', interactive=True, visible=False, type='pil')
        instructions = gr.Textbox(label=f"Instructions", value="", interactive=True, visible=True)
        with gr.Row():
            prompt_count = gr.Slider(minimum=1, maximum=5, step=1, value=1, label="Prompt count (may be inaccurate)")
            temp = gr.Slider(minimum=0, maximum=2, step=0.05, value=0.85, label="Temperature")
            top_p = gr.Slider(minimum=0, maximum=1, step=0.01, value=0.95, label="Top P")
            model = gr.Dropdown(label='Model', choices=['chatgpt-4o-latest', 'gpt-4o', 'gpt-4-turbo-2024-04-09', 'gpt-4-vision-preview'], value='chatgpt-4o-latest')
        generate = gr.Button("Generate")
        output1 = gr.Textbox(label="Output 1", value="", interactive=False, visible=True).style(show_copy_button=True)
        output2 = gr.Textbox(label="Output 2", value="", interactive=False, visible=False).style(show_copy_button=True)
        output3 = gr.Textbox(label="Output 3", value="", interactive=False, visible=False).style(show_copy_button=True)
        output4 = gr.Textbox(label="Output 4", value="", interactive=False, visible=False).style(show_copy_button=True)
        output5 = gr.Textbox(label="Output 5", value="", interactive=False, visible=False).style(show_copy_button=True)

        def update_input(mode):
            return {
                prompt: gr.update(visible=(mode != 'Describe')),
                image: gr.update(visible=(mode == 'Describe'))
            }

        def generate_prompt(prompt, instructions, prompt_count, temperature, top_p, mode, model, image):
            # Replace the templates with their associated values

            replacements = {
                '{{PROMPTMODE}}': modes[mode],
                '{{USER_PROMPT}}': prompt,
                '{{INSTRUCTIONS}}': instructions,
                '{{PROMPTCOUNT}}': str(prompt_count),
                '{{PROMPTACTION}}': mode
            }

            gen_proompt = deepcopy(base_proompt)
            for message in gen_proompt:
                if 'content' in message:
                    for placeholder, value in replacements.items():
                        message['content'] = message['content'].replace(placeholder, value)

            if mode == 'Describe':
                image = image.resize((1024, 1024))
                in_mem_file = io.BytesIO()
                image.save(in_mem_file, format = "PNG")
                in_mem_file.seek(0)
                img_bytes = in_mem_file.read()
                base64_encoded_result_bytes = base64.b64encode(img_bytes)
                base64_encoded_result_str = base64_encoded_result_bytes.decode('ascii')
                gen_proompt[-1]['content'] = [
                    {
                        "type": "text",
                        "text": "Describe my image:"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64," + base64_encoded_result_str
                        }
                    }
                ]
            # Call the OpenAI REST API using requests
            print(gen_proompt)
            response = requests.post(
                proxy + '/chat/completions',
                headers={
                    'Authorization': f'Bearer {oai_key}',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3' # cloudflare moment
                },
                json={
                    'model': model if mode != 'Describe' else 'gpt-4-vision-preview',
                    'messages': gen_proompt,
                    "temperature": temperature,
                    "top_p": top_p,
					"max_tokens": 1024
                }
            )

            # Return the generated text
            try:
                response_content = response.json()['choices'][0]['message']['content']
                print(response_content)
                generated_prompts = [
                    prompt.strip() 
                    for prompt in response_content.replace('_', ' ').split('\n') 
                    if prompt.strip()
                ]
                
                outputs = {}
                for i, (output_box) in enumerate([output1, output2, output3, output4, output5]):
                    outputs[output_box] = gr.update(
                        value=generated_prompts[i] if i < len(generated_prompts) else '',
                        visible=i < len(generated_prompts)
                    )
                
                return outputs
                
            except Exception as e:
                print(f"Error processing response: {e}")
                return {output: gr.update(value='', visible=False) for output in [output1, output2, output3, output4, output5]}

        generate.click(generate_prompt, inputs=[prompt, instructions, prompt_count, temp, top_p, mode, model, image], outputs=[output1, output2, output3, output4, output5])
        mode.change(update_input, inputs=[mode], outputs=[prompt, image])
    return [(gpt_prompt_interface, "GPT-4", "gpt_prompt_interface")]

script_callbacks.on_ui_tabs(on_ui_tabs)