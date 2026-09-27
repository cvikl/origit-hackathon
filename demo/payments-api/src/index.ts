import express from 'express';
import router from './routes';

export function createApp() {
  const app = express();
  app.use(express.json());
  app.use(router);
  return app;
}

if (require.main === module) {
  const port = process.env.PORT ? parseInt(process.env.PORT) : 3000;
  createApp().listen(port, () => {
    console.log(`payments-api listening on port ${port}`);
  });
}
