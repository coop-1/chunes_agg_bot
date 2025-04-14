import os
import boto3
import json

def clear_directory(logger, root_path, target_directory):

    target_directory = os.path.join(root_path, target_directory)
    try:
        for file in os.listdir(target_directory):
            os.remove(os.path.join(target_directory, file))
            logger.info(f'{file} removed')

        return True

    except Exception as err:
        logger.error(f'failed to remove {file} - {err}')
        return False

