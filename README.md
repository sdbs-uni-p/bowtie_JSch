# Bowtie Integration of Jsch validator by Reutter et al.

This is a integration of the JSON Schema validator [Jsch by Reutter et al.](https://jreutter.sitios.ing.uc.cl/JSch/)

## Requirements

[Docker](https://www.docker.com/) and [bowtie](https://github.com/bowtie-json-schema/bowtie/) are required.

## Running the validator

To run the validator with bowtie, the Docker image needs to be built:

```
docker build -t ghcr.io/bowtie-json-schema/jsch .
```

Next, bowtie can be executed, for instance running smoke tests:
```
bowtie smoke -i jsch 
```
