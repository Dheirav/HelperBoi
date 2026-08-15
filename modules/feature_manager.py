import os
import json
import time

MEMORY_DIR = os.path.join(os.path.dirname(__file__), '..', 'memory')
FEATURE_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', 'feature_registry.json')

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(path, data):
    """Atomically save data to a JSON file to prevent corruption."""
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    temp_path = f"{path}.tmp.{os.getpid()}_{int(time.time() * 1000)}"
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(temp_path, path)

def add_feature(feature_name, description=None):
    """Add/register a new feature in the feature registry."""
    reg = load_json(FEATURE_REGISTRY_PATH, default={})
    reg[feature_name] = True
    save_json(FEATURE_REGISTRY_PATH, reg)
    # Optionally, store description
    if description:
        desc_path = os.path.join(MEMORY_DIR, 'feature_descriptions.json')
        descs = load_json(desc_path, default={})
        descs[feature_name] = description
        save_json(desc_path, descs)
    print(f"[FEATURE] Added: {feature_name}")
    return True

def uninstall_feature(feature_name):
    """Uninstall a feature: remove from registry and optionally delete module file safely."""
    # Sanitize feature_name to prevent path traversal
    cleaned_name = feature_name.strip()
    safe_name = os.path.basename(cleaned_name)
    if safe_name != cleaned_name or '..' in cleaned_name or '/' in cleaned_name or '\\' in cleaned_name:
        print(f"[SECURITY WARNING] Path traversal blocked for feature name: {feature_name}")
        return False

    reg = load_json(FEATURE_REGISTRY_PATH, default={})
    if feature_name in reg:
        del reg[feature_name]
        save_json(FEATURE_REGISTRY_PATH, reg)
        print(f"[FEATURE] Uninstalled: {feature_name}")
        
        # Verify module path is inside modules directory
        modules_dir = os.path.realpath(os.path.dirname(__file__))
        module_path = os.path.realpath(os.path.join(modules_dir, f'{safe_name}.py'))
        if os.path.commonpath([module_path, modules_dir]) != modules_dir:
            print(f"[SECURITY WARNING] Attempted access outside modules directory blocked: {module_path}")
            return False

        if os.path.exists(module_path):
            try:
                os.remove(module_path)
                print(f"[FEATURE] Module file deleted: {module_path}")
            except Exception as e:
                print(f"[FEATURE] Could not delete module file: {e}")
        return True
    print(f"[FEATURE] Not found: {feature_name}")
    return False

