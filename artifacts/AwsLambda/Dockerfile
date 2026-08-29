FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

RUN pip install --no-cache-dir pandas

COPY lambda.py .

CMD ["lambda.lambda_handler"]