const HOST_IP = '172.20.10.2';
export const API_BASE_URL = `/api`;
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
export const WS_BASE_URL = `${wsProtocol}//${window.location.host}`;
