build:
	docker build -t colunch-app:latest .

run:
	docker run --rm -it -e OPENAI_API_KEY -e PINECONE_API_KEY -e COLUNCH_HOST="0.0.0.0" -e COLUNCH_PORT="8000" -p 8000:8000 colunch-app:latest
