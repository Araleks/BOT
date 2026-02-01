import os
from datetime import datetime

# === КОНФИГУРАЦИЯ ===

INCLUDE_DIRS = [
    "setups",
    "utils",
    "handlers",
]

ALLOWED_EXTENSIONS = {".py", ".env"}

EXCLUDE_DIRS = {".venv", "__pycache__", ".git"}

OUTPUT_FILENAME = "project_snapshot.txt"


def should_include_file(path: str) -> bool:
    _, ext = os.path.splitext(path)
    return ext in ALLOWED_EXTENSIONS


def walk_and_collect(base_dir: str) -> list[tuple[str, str]]:
    collected = []

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for fname in files:
            abs_path = os.path.join(root, fname)
            rel_path = os.path.relpath(abs_path, start=".")

            if should_include_file(abs_path):
                collected.append((abs_path, rel_path))

    return collected


def read_file_safely(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="cp1251") as f:
                return f.read()
        except Exception as e:
            return f"<<Ошибка чтения файла (кодировка): {e}>>"
    except Exception as e:
        return f"<<Ошибка чтения файла: {e}>>"


def main():
    all_files = []

    # 0. Автоматически добавляем все .py и .env файлы из корня
    for fname in os.listdir("."):
        if os.path.isfile(fname) and should_include_file(fname):
            abs_path = os.path.abspath(fname)
            rel_path = fname
            if (abs_path, rel_path) not in all_files:
                all_files.append((abs_path, rel_path))

    # 1. Обходим указанные папки
    for d in INCLUDE_DIRS:
        if not os.path.isdir(d):
            continue
        collected = walk_and_collect(d)
        for abs_path, rel_path in collected:
            if (abs_path, rel_path) not in all_files:
                all_files.append((abs_path, rel_path))

    # 2. Сортируем
    all_files.sort(key=lambda x: x[1])

    # 3. Пишем в файл
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = [
        "PROJECT SNAPSHOT",
        f"Generated at: {now_str}",
        "",
        "Included files:",
    ]
    for _, rel_path in all_files:
        header.append(f"  - {rel_path}")
    header.append("\n" + "=" * 80 + "\n")

    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as out:
        out.write("\n".join(header))

        for abs_path, rel_path in all_files:
            out.write(f"\n{'=' * 80}\n")
            out.write(f"FILE: {os.path.basename(rel_path)}\n")
            out.write(f"PATH: {rel_path}\n")
            out.write(f"{'=' * 80}\n\n")

            content = read_file_safely(abs_path)
            out.write(content)
            out.write("\n\n")

    print(f"✅ Снимок проекта сохранён в файл: {OUTPUT_FILENAME}")
    print(f"Всего файлов: {len(all_files)}")


if __name__ == "__main__":
    main()
