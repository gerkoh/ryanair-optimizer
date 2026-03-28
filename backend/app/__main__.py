import uvicorn


def main() -> None:
    uvicorn.run("app.main:app", host="localhost", port=8000)


if __name__ == "__main__":
    main()
