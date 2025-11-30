import os

extensions = ['.py', '.html', '.css', '.js'] # Расширения, которые берем
output_file = 'full_project.txt'

with open(output_file, 'w', encoding='utf-8') as outfile:
    for root, dirs, files in os.walk("."):
        # Игнорируем папку виртуального окружения и git
        if 'venv' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                path = os.path.join(root, file)
                outfile.write(f"\n--- FILE: {path} ---\n") # Разделитель
                try:
                    with open(path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"Error reading file: {e}")

print(f"Готово! Весь код в файле {output_file}")