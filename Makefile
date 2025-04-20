VERSION=v0.1.0
IMAGE_NAME=jsonexcel-viewer

.PHONY: build run clean up down
build:
	docker build -t $(IMAGE_NAME):$(VERSION) -f develop/Dockerfile .

run:
	python main.py

clean:
	docker rmi $(IMAGE_NAME):$(VERSION)

up:
	@cd develop && docker-compose up -d

down:
	@cd develop && docker-compose down