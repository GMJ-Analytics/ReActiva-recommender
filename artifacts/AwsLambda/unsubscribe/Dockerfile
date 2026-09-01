FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

RUN pip install --no-cache-dir \
    boto3==1.43.56 \
    botocore==1.43.56 \
    pandas==3.0.5 \
    python-dotenv==1.2.2

COPY src/reactiva/ ${LAMBDA_TASK_ROOT}/reactiva/

COPY artifacts/AwsLambda/unsubscribe/lambda.py ${LAMBDA_TASK_ROOT}/lambda.py

CMD ["lambda.lambda_handler"]