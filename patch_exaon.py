import os
import glob

def patch_exaone():
    # Search for all configuration_exaone.py files in the Hugging Face cache
    base_path = "/home/ai-kyw-dev/.cache/huggingface/modules/transformers_modules/**/configuration_exaone.py"
    files = glob.glob(base_path, recursive=True)
    
    if not files:
        print("[-] No configuration_exaone.py files found in the cache.")
        return

    for file_path in files:
        print(f"[*] Processing {file_path}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Fix 1: Ensure RopeParameters is a class, not None
        # We look for the common pattern in EXAONE configuration files
        old_pattern = "except ImportError:\n    RopeParameters = None"
        new_pattern = "except ImportError:\n    class RopeParameters:\n        pass"
        
        # Another possible pattern (nested try as seen in previous attempts)
        old_pattern_v2 = "    try:\n    from transformers.modeling_rope_utils import RopeParameters\nexcept ImportError:\n    class RopeParameters:\n        pass\nexcept ImportError:\n    RopeParameters = None"
        new_pattern_v2 = "try:\n    from transformers.modeling_rope_utils import RopeParameters\nexcept ImportError:\n    class RopeParameters:\n        pass"

        if old_pattern_v2 in content:
            updated_content = content.replace(old_pattern_v2, new_pattern_v2)
            print(f" [+] Found and fixed nested/broken RopeParameters block.")
        elif old_pattern in content:
            updated_content = content.replace(old_pattern, new_pattern)
            print(f" [+] Found and fixed RopeParameters = None assignment.")
        else:
            # If we didn't find the pattern, let's try a more surgical regex-like replacement
            # but safer to check line by line
            lines = content.splitlines()
            changed = False
            for i in range(len(lines)):
                if "RopeParameters = None" in lines[i] and i > 0 and "except ImportError" in lines[i-1]:
                    lines[i] = "    class RopeParameters:\n        pass"
                    changed = True
            
            if changed:
                updated_content = "\n".join(lines)
                print(f" [+] Fixed RopeParameters line by line.")
            else:
                print(f" [!] Pattern not found in {file_path}. Checking line 156...")
                # Fallback: just remove the type hint if it's causing the crash
                if "rope_parameters: RopeParameters | None = None" in content:
                    updated_content = content.replace("rope_parameters: RopeParameters | None = None", "rope_parameters = None")
                    print(f" [+] Replaced type hint at line 156 to avoid TypeError.")
                else:
                    print(f" [-] Could not identify the problematic code in {file_path}.")
                    continue

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        print(f" [OK] Patched successfully.")

if __name__ == "__main__":
    patch_exaone()