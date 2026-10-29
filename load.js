import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  vus: 50,
  duration: '5m',
};

export default function () {
  http.get('http://api:8080/stream/authorize?user_id=123&movie_id=dune2');
  sleep(0.1);
}
