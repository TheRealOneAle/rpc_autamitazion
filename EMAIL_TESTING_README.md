# EMAIL_TESTING_README

## How to test email sending

### Mock Mode (Default)
Without SMTP credentials, emails are not sent but logged as [mock].

1. Generate ranking: curl -X POST http://localhost:5002/generate
2. Watch logs: docker compose logs -f notificacion-ranking-service

### Real Mode
Create .env file with SMTP credentials:
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your-email@gmail.com
  SMTP_PASS=your-app-password
  FROM_ADDR=your-email@gmail.com

Then recreate: docker compose up -d --force-recreate notificacion-ranking-service

