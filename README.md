## deploy
### webhook
```
gcloud beta functions deploy webhook --entry-point callback --trigger-http --runtime python37 --region asia-northeast1 --env-vars-file ../.env --max-instances=60

```

### reminder
```
gcloud beta functions deploy reminder --entry-point remind --trigger-http --runtime python37 --region asia-northeast1 --env-vars-file ../.env --max-instances=60
```
