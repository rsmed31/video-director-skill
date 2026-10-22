#!/usr/bin/env node
// Installs the video-director skill into an agent's skills folder.
//   npx video-director-skill                 -> ~/.claude/skills/video-director
//   npx video-director-skill --codex         -> ~/.codex/skills/video-director
//   npx video-director-skill --dir <path>    -> <path>/video-director
//   npx video-director-skill --project       -> ./.claude/skills/video-director
// An existing director.yaml (your learned memory) is never overwritten; the new starter is saved
// next to it as director.starter.yaml so you can merge new defaults by hand.
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

const args = process.argv.slice(2);
if (args.includes('-h') || args.includes('--help')) {
  console.log('usage: npx video-director-skill [--codex | --project | --dir <path>] [--force-memory]');
  process.exit(0);
}
const src = path.join(__dirname, '..', 'skills', 'video-director');
let root = path.join(os.homedir(), '.claude', 'skills');
if (args.includes('--codex')) root = path.join(os.homedir(), '.codex', 'skills');
if (args.includes('--project')) root = path.join(process.cwd(), '.claude', 'skills');
const di = args.indexOf('--dir');
if (di !== -1 && args[di + 1]) root = path.resolve(args[di + 1]);
const dest = path.join(root, 'video-director');
const forceMemory = args.includes('--force-memory');

function copy(from, to) {
  const st = fs.statSync(from);
  if (st.isDirectory()) {
    if (path.basename(from) === '__pycache__') return;
    fs.mkdirSync(to, { recursive: true });
    for (const f of fs.readdirSync(from)) copy(path.join(from, f), path.join(to, f));
    return;
  }
  if (path.basename(from) === 'director.yaml' && fs.existsSync(to) && !forceMemory) {
    fs.copyFileSync(from, path.join(path.dirname(to), 'director.starter.yaml'));
    console.log('  kept your director.yaml (memory); new defaults in director.starter.yaml');
    return;
  }
  fs.copyFileSync(from, to);
}

copy(src, dest);
console.log(`video-director installed -> ${dest}`);
console.log('Needs: Python 3 with PyYAML (pip install pyyaml), ffmpeg, Node 22+ for HyperFrames.');
console.log('Also install the HyperFrames skills it builds with: npx skills add heygen-com/hyperframes');
