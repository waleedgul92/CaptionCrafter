import argparse
from deep_translator import GoogleTranslator

def translate_text(text, dest_language):
    # Initialize the Translator and translate the text
    translated = GoogleTranslator(source='auto', target=dest_language).translate(text)
    return translated

def batch_translate(file_path, dest_language, sentences_per_batch=50):
    translated_texts = []
    
    # Read the file with explicit encoding
    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()
        
        # Split the text into sentences
        sentences = text.split('. ')  # Adjust the sentence delimiter as needed
        
        # Process sentences in batches
        for i in range(0, len(sentences), sentences_per_batch):
            batch = sentences[i:i + sentences_per_batch]
            # Join the batch into a single string
            batch_text = '. '.join(batch)
            translated_batch = translate_text(batch_text, dest_language)
            translated_texts.append(translated_batch)
    
    # Join the translated batches into a single string
    return '. '.join(translated_texts)

def save_translated_text(translated_text, output_file_path):
    # Save the translated text to a file
    with open(output_file_path, "w", encoding="utf-8") as file:
        file.write(translated_text)

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Translate text from a file.')
    parser.add_argument('input_file', type=str, help='Path to the input file containing text to translate.')
    parser.add_argument('dest_language', type=str, help='Destination language code (e.g., "en" for English).')

    # Parse the command line arguments
    args = parser.parse_args()
    
    # Get the translated text
    translated_text = batch_translate(args.input_file, args.dest_language)
    
    # Print the translated text

    
    out_file = args.input_file.split('.')[0] + f"_translated_{args.dest_language}.txt"
    # Save the translated text to a file
    save_translated_text(translated_text,out_file)
    print(f"Translated text saved to {out_file}")
