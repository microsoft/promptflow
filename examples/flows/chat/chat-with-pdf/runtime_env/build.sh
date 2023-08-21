registry_name=docker.io/modulesdkpreview
image_tag=chat_with_pdf

docker build -t "$image_tag" .

docker_image_tag=$registry_name/$image_tag

echo "Docker image tag: $docker_image_tag"
docker tag "$image_tag" "$docker_image_tag"
image_tag=$docker_image_tag

echo "Start pushing image...$image_tag"
docker push "$image_tag"