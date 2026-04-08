import { datadogRum } from '@datadog/browser-rum';
import { datadogLogs } from '@datadog/browser-logs';
import { reactPlugin } from '@datadog/browser-rum-react';

export function initDatadog() {
  datadogRum.init({
    applicationId: 'VITE_DD_APP_ID_PLACEHOLDER',
    clientToken: 'VITE_DD_CLIENT_TOKEN_PLACEHOLDER',
    site: 'datadoghq.com',
    service: 'ddstore-frontend',
    env: 'demo',
    version: '1.0.0',
    sessionSampleRate: 100,
    sessionReplaySampleRate: 100,
    trackResources: true,
    trackUserInteractions: true,
    trackLongTasks: true,
    plugins: [reactPlugin({ router: false })],
  });

  datadogLogs.init({
    clientToken: 'VITE_DD_CLIENT_TOKEN_PLACEHOLDER',
    site: 'datadoghq.com',
    service: 'ddstore-frontend',
    env: 'demo',
    version: '1.0.0',
    forwardErrorsToLogs: true,
    sessionSampleRate: 100,
  });

  datadogRum.startSessionReplayRecording();
}

export const logger = {
  info: (msg, ctx) => datadogLogs.logger.info(msg, ctx),
  warn: (msg, ctx) => datadogLogs.logger.warn(msg, ctx),
  error: (msg, ctx) => datadogLogs.logger.error(msg, ctx),
};
