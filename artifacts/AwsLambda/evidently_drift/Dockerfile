FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

RUN pip install --no-cache-dir \
    aiobotocore==3.9.0 \
    boto3==1.43.56 \
    botocore==1.43.56 \
    evidently==0.7.21 \
    numpy==2.4.6 \
    pandas==3.0.5 \
    python-dotenv==1.2.2 \
    s3fs==2026.7.0

COPY src/reactiva/ ${LAMBDA_TASK_ROOT}/reactiva/

COPY artifacts/AwsLambda/evidently_drift/lambda.py ${LAMBDA_TASK_ROOT}/lambda.py

CMD ["lambda.lambda_handler"]