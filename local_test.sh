#!/bin/bash

function clean {
  curl -X DELETE 'http://localhost:5001/reset' -H "X-Authorization: $stripped_string"
}

function getall {
  curl -X POST 'http://localhost:5001/artifacts' \
  -H "X-Authorization: $stripped_string" \
  -H 'Content-Type: application/json' \
  -d '{"name": "*", "types": []}'
}

response=$(curl -X PUT http://localhost:5001/authenticate \
  -H "Content-Type: application/json" \
  -d '{
        "user": {
            "name": "ece30861defaultadminuser",
            "is_admin": true
        },
        "secret": {
            "password": "correcthorsebatterystaple123(!__+@**(A'\''\"`;DROP TABLE packages;"
        }
      }')

stripped_string="${response//\"/}"

echo $stripped_string

clean

response=$(curl -X POST 'http://localhost:5001/artifact/model' \
  -H "X-Authorization: $stripped_string" \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://huggingface.co/google-bert/bert-base-uncased"}')

bert_id=$(echo $response | jq -r '.metadata.id')
echo "BERT ID: $bert_id"

curl -X POST 'http://localhost:5001/artifact/dataset' \
  -H "X-Authorization: $stripped_string" \
  -H 'Content-Type: application/json' \
  -d '{ "name": "bookcorpus", "url": "https://huggingface.co/datasets/bookcorpus/bookcorpus"}'

curl -X POST 'http://localhost:5001/artifact/model' \
  -H "X-Authorization: $stripped_string" \
  -H 'Content-Type: application/json' \
  -d ' {"name": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab", "url": "https://huggingface.co/parthvpatil18/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab"}'


curl -X PUT "http://localhost:5001/artifacts/model/$bert_id" \
  -H "X-Authorization: $stripped_string" \
  -H 'Content-Type: application/json' \
  -d '{
      "metadata": {
        "name": "string",
        "id": "48472749248",
        "type": "model"
      },
      "data": {
        "url": "https://huggingface.co/openai/whisper-tiny/tree/main",
        "download_url": "https://ec2-10-121-34-12/download/whisper-tiny"
      }
}'

getall

# curl -X DELETE "http://localhost:5001/artifacts/model/48472749248" \
#   -H "X-Authorization: $stripped_string"

# getall

curl -X GET "http://localhost:5001/artifact/byName/bookcorpus" \
  -H "X-Authorization: $stripped_string"

curl -X POST "http://localhost:5001/artifact/byRegEx" \
  -H "X-Authorization: $stripped_string" \
    -H 'Content-Type: application/json' \
    -d '{"regex": "(a|aa)*"}'

curl -X POST "http://localhost:5001/artifact/byRegEx" \
  -H "X-Authorization: $stripped_string" \
    -H 'Content-Type: application/json' \
    -d '{"regex": "(a+)+$"}'

curl -X POST "http://localhost:5001/artifact/byRegEx" \
  -H "X-Authorization: $stripped_string" \
    -H 'Content-Type: application/json' \
    -d '{"regex": "(a{1,99999}){1,99999}$"}'

curl -X POST "http://localhost:5001/artifact/byRegEx" \
  -H "X-Authorization: $stripped_string" \
    -H 'Content-Type: application/json' \
    -d '{"regex": "string"}'