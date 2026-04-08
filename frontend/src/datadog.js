import { datadogRum } from '@datadog/browser-rum';
import { datadogLogs } from '@datadog/browser-logs';
import { reactPlugin } from '@datadog/browser-rum-react';

export function initDatadog() {
  datadogRum.init({
    applicationId: import.meta.env.VITE_DD_APP_ID,
    clientToken: import.meta.env.VITE_DD_CLIENT_TOKEN,
    site: import.meta.env.VITE_DD_SITE || 'datadoghq.com',
    service: import.meta.env.VITE_DD_SERVICE || 'ddstore-frontend',
    env: import.meta.env.VITE_DD_ENV || 'demo',
    version: import.meta.env.VITE_DD_VERSION || '1.0.0',
    sessionSampleRate: 100,
    sessionReplaySampleRate: 100,
    trackResources: true,
    trackUserInteractions: true,
    trackLongTasks: true,
    defaultPrivacyLevel: 'allow',
    plugins: [reactPlugin({ router: false })],
  });

  datadogLogs.init({
    clientToken: import.meta.env.VITE_DD_CLIENT_TOKEN,
    site: import.meta.env.VITE_DD_SITE || 'datadoghq.com',
    service: import.meta.env.VITE_DD_SERVICE || 'ddstore-frontend',
    env: import.meta.env.VITE_DD_ENV || 'demo',
    version: import.meta.env.VITE_DD_VERSION || '1.0.0',
    forwardErrorsToLogs: true,
    sessionSampleRate: 100,
  });

  datadogRum.startSessionReplayRecording();

  // Pick up user context injected by Playwright RUM loadgen
  if (window.__DD_USER__) {
    datadogRum.setUser(window.__DD_USER__);
  }
}

export const logger = {
  info: (msg, ctx) => datadogLogs.logger.info(msg, ctx),
  warn: (msg, ctx) => datadogLogs.logger.warn(msg, ctx),
  error: (msg, ctx) => datadogLogs.logger.error(msg, ctx),
};
