from module_a import ConfigManager as ConfigManagerA
from module_b import load_config
from submodule.module_c import ConfigManager as ConfigManagerC

def main():
    
    print(load_config())  # 调用 module_b 的 load_config
    manager_a = ConfigManagerA()
    print(manager_a.load_config())  # 调用 module_a.ConfigManager 的 load_config

    manager_c = ConfigManagerC()
    print(manager_c.load_config())  # 调用 submodule.module_c.ConfigManager 的 load_config

if __name__ == "__main__":
    main()
