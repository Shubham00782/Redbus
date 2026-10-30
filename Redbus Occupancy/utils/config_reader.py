import configparser
import os

class ConfigReader:
    @staticmethod
    def read_config(section, key):
        config = configparser.ConfigParser()
        # Get absolute path to config.ini
        base_dir = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(base_dir, 'config', 'config.ini')
        config.read(config_path)
        return config.get(section, key)
