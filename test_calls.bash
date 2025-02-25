python multi_lora_inference.py \
    --character_trigger "GRIMESLORA" \
    --environment_trigger "MONACOLORA" \
    --object_trigger "STANLEYLORA" \
    --output_name "lora_inference_images/grimes_monaco_stanley" \
    --prompt_template "GRIMESLORA surfing at MONACOLORA while holding STANLEYLORA" \
    --lora_character_path trained_lora_config/GRIMESLORA_output_20250223_103045.json \
    --lora_environment_path trained_lora_config/MONACOLORA_output_20250223_105630.json \
    --lora_object_path trained_lora_config/STANLEYLORA_output_20250223_110827.json

python multi_lora_inference.py \
    --character_trigger "GRIMESLORA" \
    --object_trigger "STANLEYLORA" \
    --output_name "lora_inference_images/grimes_monaco_stanley" \
    --prompt_template "GRIMESLORA surfing while holding STANLEYLORA" \
    --lora_character_path trained_lora_config/GRIMESLORA_output_20250223_103045.json \
    --lora_object_path trained_lora_config/STANLEYLORA_output_20250223_110827.json