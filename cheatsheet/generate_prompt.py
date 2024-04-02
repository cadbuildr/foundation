import json
import os
import ast

GROUPS_FILE = "groups.json"
PATH_PROJECT = "../src/foundation/"
OUTPUT_FILE = "prompt.md"


def read_json(file_name):
    """Read a json file"""
    with open(file_name, "r") as file:
        data = json.load(file)
    return data


def read_files(path):
    """Open all file in the path with .py extension and read them"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path {path} does not exist")
    files = {}

    for root, _, filenames in os.walk(path):
        for filename in filenames:
            if filename.endswith(".py"):
                with open(os.path.join(root, filename), "r") as file:
                    files[filename] = file.read()
    return files


def select_group(groups):
    """Select a group from the list"""

    while True:
        print("Select a group:")
        for i, group in enumerate(groups):
            print(f"{i+1}: {group}")
        try:
            group_index = int(input("Enter the group number: ")) - 1
            if group_index < 0 or group_index >= len(groups):
                raise ValueError
            break
        except ValueError:
            print("Invalid group number\n")
    return groups[group_index]


def get_classes(file_str):
    """Parce a file and return all classes"""

    classes = {}
    tree = ast.parse(file_str)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes[node.name] = ast.get_source_segment(file_str, node)
    return classes


def grab_class(files, group):
    """Reads all files and searches for the class definition. Repeat for all elements in group"""

    found_classes = {}
    for file_name, file_str in files.items():
        classes = get_classes(file_str)

        for class_name, class_str in classes.items():
            if class_name in group:
                print(f"Found class {class_name} in file {file_name}")
                found_classes[class_name] = class_str

    # see if any classes have not been found
    for class_name in group:
        if class_name not in found_classes:
            print(f"\033[91mClass {class_name} not found !\033[0m")
            exit(1)
    print()

    return found_classes


def get_prompt(class_str, name):
    """Generate a prompt for a class"""

    prompt = (
        "Please generate a CheatSheet for documenting Python classes from a library. The CheatSheet is titled "
        + name
        + ".\n\n"
        "Instructions:\n"
        "1. Title:" + name + "\n"
        "2. Objective: To document all classes in the library\n"
        "3. Format: Markdown (.md)\n"
        "4. Key Points:\n"
        "   - Each method should be explained with a brief description.\n"
        "   - Ensure all types of arguments and return values are clearly displayed.\n"
        "   - I want tests for all classes.\n"
        "5. Language: English\n\n"
    )

    for class_name, class_str in class_str.items():
        prompt += f"Class {class_name}:\n```python\n{class_str}\n```\n\n"
    return prompt


def save_prompt(prompt):
    """Save the prompt to a file"""
    with open("prompt.md", "w") as file:
        file.write(prompt)
    print("Prompt saved to prompt.md")


if __name__ == "__main__":
    try:
        groups = read_json(GROUPS_FILE)
        files = read_files(PATH_PROJECT)
    except Exception as e:
        print(e)
        exit(1)

    group = select_group(list(groups.keys()))
    print(f"\nSelected group: {group}\n\n")

    class_str = grab_class(files, groups[group])
    generated_prompt = get_prompt(class_str, group)

    save_prompt(generated_prompt)
