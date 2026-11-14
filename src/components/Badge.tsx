export type Provenance = 'real' | 'demo'
/** Small provenance marker: "Real" = from real data, "Demo" = mock / synthetic. */
export default function Badge({ kind }: { kind: Provenance }) {
  return <span className={`badge ${kind}`} title={kind === 'real' ? 'From real data' : 'Mock / synthetic data'}>{kind === 'real' ? 'Real' : 'Demo'}</span>
}
