import uvicorn


if __name__ == '__main__':
    uvicorn.run('pydantic_backend.app:app', host='0.0.0.0', port=8011, reload=True)
