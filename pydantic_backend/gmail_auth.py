from .config import get_settings
from .ingestion.gmail import authorize


if __name__ == '__main__':
    authorize(get_settings())
    print('Gmail authorization complete. Refresh token saved outside Git.')
