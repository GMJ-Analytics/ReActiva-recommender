FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}


COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

    

COPY src/reactiva/ ${LAMBDA_TASK_ROOT}/reactiva/

COPY artifacts/AwsLambda/campaign_sender/lambda.py ${LAMBDA_TASK_ROOT}/lambda.py

CMD ["lambda.lambda_handler"]