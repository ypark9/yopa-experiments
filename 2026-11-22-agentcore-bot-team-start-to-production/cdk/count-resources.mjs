// Counts the resources in the synthesized template, by type, without CDK's own metadata.
import fs from 'node:fs';
const template = JSON.parse(fs.readFileSync(new URL('./cdk.out/BotTeamMinimal.template.json', import.meta.url)));
const types = Object.values(template.Resources).map((r) => r.Type).filter((t) => t !== 'AWS::CDK::Metadata');
const counts = {};
for (const t of types) counts[t] = (counts[t] ?? 0) + 1;
for (const [t, n] of Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))) {
  console.log(String(n).padStart(3), t);
}
console.log(String(types.length).padStart(3), 'TOTAL (AWS::CDK::Metadata excluded)');
