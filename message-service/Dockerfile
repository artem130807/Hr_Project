# syntax=docker/dockerfile:1

FROM golang:1.24-alpine AS builder

WORKDIR /src
RUN apk add --no-cache git ca-certificates

# go.mod may require a newer toolchain; Go will download it automatically.
ENV GOTOOLCHAIN=auto

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /out/message-service ./cmd/api

FROM alpine:3.20

RUN apk add --no-cache ca-certificates tzdata \
  && adduser -D -H -u 10001 appuser

WORKDIR /app
COPY --from=builder /out/message-service /app/message-service

USER appuser
EXPOSE 8080

ENTRYPOINT ["/app/message-service"]
