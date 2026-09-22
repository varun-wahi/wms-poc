#!/usr/bin/env bash
# Run in Cloud Shell from the repo root:  bash lab_setup.sh
set -uo pipefail
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION=us-central1
DB_PASS='WmsPoc2026x'            # postgres admin password (no commas/special chars)
PROJ_NUM=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
echo ">> Project: $PROJECT_ID ($PROJ_NUM)"

echo ">> 1/6 Enabling APIs"
gcloud services enable alloydb.googleapis.com aiplatform.googleapis.com run.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com servicenetworking.googleapis.com \
  compute.googleapis.com

echo ">> 2/6 Starting AlloyDB (runs in background while we deploy)"
gcloud compute addresses create google-managed-services-default --global \
  --purpose=VPC_PEERING --prefix-length=16 --network=default 2>&1 | tail -1
gcloud services vpc-peerings connect --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services-default --network=default 2>&1 | tail -1
gcloud alloydb clusters create wms-cluster --region=$REGION --network=default --password="$DB_PASS" 2>&1 | tail -2
gcloud alloydb instances create wms-primary --cluster=wms-cluster --region=$REGION \
  --instance-type=PRIMARY --cpu-count=2 --async 2>&1 | tail -2

echo ">> 3/6 Granting Gemini access to Cloud Run's service account"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJ_NUM}-compute@developer.gserviceaccount.com" \
  --role=roles/aiplatform.user --condition=None >/dev/null

echo ">> 4/6 Deploying agent to Cloud Run (DB host filled in later)"
gcloud run deploy wms-agent --source . --region $REGION --no-allow-unauthenticated \
  --network default --subnet default --vpc-egress private-ranges-only \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,DB_NAME=postgres,DB_USER=wms_reader,DB_PASSWORD=reader_pw,DB_HOST=placeholder" \
  --quiet || { echo "!! Deploy failed - fix the error above, then re-run this script"; exit 1; }

echo ">> 5/6 Waiting for AlloyDB instance to be READY (can take 10-20 min)"
until [ "$(gcloud alloydb instances describe wms-primary --cluster=wms-cluster --region=$REGION --format='value(state)' 2>/dev/null)" = "READY" ]; do
  echo "   ...not ready yet"; sleep 30
done
DB_IP=$(gcloud alloydb instances describe wms-primary --cluster=wms-cluster --region=$REGION --format='value(ipAddress)')
echo
echo "=============================================================="
echo " AlloyDB private IP: $DB_IP"
echo " MANUAL STEP: Console > AlloyDB > wms-cluster > AlloyDB Studio"
echo "   database=postgres  user=postgres  password=$DB_PASS"
echo "   Run schema.sql, THEN seed.sql (open each file with: cat schema.sql)"
echo "=============================================================="
read -r -p "Press Enter after both scripts ran successfully... "

echo ">> 6/6 Pointing Cloud Run at AlloyDB"
gcloud run services update wms-agent --region $REGION --update-env-vars "DB_HOST=$DB_IP" --quiet
echo
echo "DONE. Start the demo UI with:"
echo "  gcloud run services proxy wms-agent --region $REGION --port 8080"
echo "then Web Preview > Preview on port 8080 > choose wms_agent"
