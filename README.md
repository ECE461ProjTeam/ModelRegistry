# Trustworthy Model Registry

We have created a custom model registry for storing, evaluating, and downloading machine learning models from HuggingFace, the datasets they may be trained on, as well as their respective GitHub code repositories. The application is deployed using AWS services. For more information on the deployment, please check the Deployment section. The webpage has options to upload artifacts, view the list of all artifacts, filter them by name or regular expression, download models, and rate them. Once the server is provided with an upload query consisting of a HuggingFace link, it fetches the model’s metadata, rates the model using the BSS tool, downloads the files, zips them and sends them to store in an S3 bucket. The artifact entry is saved in a PostgreSQL database, hosted through Aurora Serverless. The user can choose to query this database with several filtering options, as well as download it, view its size cost, lineage, and license compatibility. This registry allows for a custom, private database to store only the models ACME Corporation wishes to use, having to pass through rigorous testing before being accepted, and therefore having a reliability advantage over publicly available model management software. The systems also allows an admin to carefully curate users and their respective permissions, ensuring security within the corporation. 

## Quick start
### Set up virtual environment and install dependencies for the backend
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
### Install dependencies for the frontend
```
cd frontend
npm install
```

### Set up environment variables
- `LOG_FILE` - Name of the log file
- `LOG_VERBOSITY` - Verbosity of logging (0 - silent, 1 - INFO, 2 - DEBUG)
- `GITHUB_TOKEN` - Your GitHub token
- `GEN_AI_STUDIO_API_KEY` - Purdue GenAI Studio API key 
- `AWS_CONFIG_FILE=.aws/config`
- `AWS_ACCESS_KEY_ID` - Access Key ID for IAM Role with necessary permissions
- `AWS_SECRET_ACCESS_KEY` - Secret Key for IAM Role with necessary permissions
- `AWS_REGION` - Region for hosting all your AWS components (default: us-east-2)
- `BUCKET_NAME` - Bucket name for downloading models (Model Ingestion)
- `ELASTIC_BEANSTALK_ENV_NAME` - Name of the Elastic Beanstalk Environment managing the application
- `DB_CLUSTER_IDENTIFIER` - Database cluster containing the application's database. 
- `CLOUDWATCH_LOG_GROUP` - Log group for application logs (stdout)

Note: You can obtain the `GEN_AI_STUDIO_API_KEY` at https://genai.rcac.purdue.edu/ by logging in to your Purdue student account, click on your profile -> Settings -> Account -> API Keys and then create one.

Here are some additional environment variables that you might want to use for local testing:
- `DEBUG` 
- `PORT`
- `JWT_SECRET_KEY`
- `SECRET_KEY`

### Run API server for local testing

```
run api
```

### Run frontend for local testing
In order to run the frontend locally (for testing), run the following command in the `frontend` directory:
```
npm run dev
```

## Deployment
### Frontend
The frontend of our application can be found at: https://main.d2nna2oc3t9x3b.amplifyapp.com
### Backend (API)
The backend of our application can be found at: https://hqtrtl2qf1.execute-api.us-east-2.amazonaws.com

### AWS Components used for Deployment:
1. Elastic Beanstalk: Elastic Beanstalk is a Platform-as-a-Service (PaaS) offered by AWS that makes it easy to deploy and manage web applications and services. It allows us to set up the application with load balancing and auto scaling, and it also made it easier for us to continuously deploy the application since it would fetch the code from an S3 bucket and deploy to the EB environment by creating the EC2 instances on its own.
2. EC2: We use EC2 as the compute for running the backedn of our application. Elastic Beanstalk manages and creates EC2 instances that host the application's backend. It will auto-scale the number of instances based on traffic and it will also implement load-balancing across all instances.
3. Aurora Serverlessv2: We use as serverless PostgreSQL database since it would be safer and cheaper to use.
4. S3: S3 is used for file storage for model ingestion. Another S3 bucker is also used as part of the CI/CD pipeline. The latest version of the code is copied to an S3 bucket and then the contents of the bucket are use to update teh Elastic Beanstalk environemnt and redploy the application.
5. Cloudwatch: We use Cloudwatch for logging purposes.
6. Amplify: We use AWS Amplify to deploy the frontend of the application. Amplify is connected to the repository and monitors is for any changes. Each time a PR is merged, Amplify will update the frontend to reflect the changes as well.
7. API Gateway: To prevent mixed content errors (with the frontend being HTTPS and backend being HTTP), we added API Gateway as a proxy

### Deployment Diagram
Figure 1 showcases the deployment design for AWS. 
<figure>
  <img width="3436" height="2300" alt="AWS Diagram" src="https://github.com/user-attachments/assets/378db54b-a26d-4e88-8c3f-ebc45896da5a" />
  <figcaption><strong>Fig 1.</strong> AWS Deployment Diagram.</figcaption>
</figure>

