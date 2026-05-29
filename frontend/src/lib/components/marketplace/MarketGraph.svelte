<script lang="ts">
  // d3 표준 force-directed graph.
  // drag / zoom 은 d3-drag, d3-zoom 라이브러리 그대로 사용 (커스텀 핸들러 없음).
  import { onMount, onDestroy } from 'svelte';
  import {
    forceSimulation,
    forceManyBody,
    forceLink,
    forceCenter,
    forceCollide,
    forceX,
    forceY,
    type Simulation,
  } from 'd3-force';
  import { drag } from 'd3-drag';
  import { zoom, zoomIdentity, type ZoomTransform } from 'd3-zoom';
  import { select } from 'd3-selection';

  type SvcInput = {
    id: string;
    name: string;
    vendor: string;
    category: string;
    categoryLabel: string;
    color: string;
    calls: number;
    latency: number | null;
  };

  interface Props {
    services: SvcInput[];
    width?: number;
    height?: number;
    selectedId?: string | null;
    onSelect?: (svc: SvcInput) => void;
  }
  const {
    services,
    width = 1000,
    height = 360,
    selectedId = null,
    onSelect,
  }: Props = $props();

  type Node = {
    id: string;
    color: string;
    radius: number;
    label: string;
    svc: SvcInput;
    category: string;
    x?: number; y?: number; vx?: number; vy?: number; fx?: number | null; fy?: number | null;
  };
  type Link = { source: string | Node; target: string | Node };

  // ─── 데이터 ────────────────────────────────────────────────────────────
  const nodes = $derived.by<Node[]>(() =>
    services.map((s) => ({
      id: s.id,
      color: s.color,
      radius: 5 + Math.log1p(s.calls / 500) * 1.3,
      label: s.name,
      svc: s,
      category: s.category,
    })),
  );

  const categories = $derived.by(() => {
    const m = new Map<string, { color: string; label: string; count: number }>();
    for (const s of services) {
      const prev = m.get(s.category) ?? { color: s.color, label: s.categoryLabel, count: 0 };
      prev.count += 1;
      m.set(s.category, prev);
    }
    return [...m.entries()].map(([key, v]) => ({ key, ...v }));
  });

  // 같은 카테고리끼리 invisible star link — cluster 강제.
  const links = $derived.by<Link[]>(() => {
    const out: Link[] = [];
    const groups = new Map<string, string[]>();
    for (const n of nodes) {
      const arr = groups.get(n.category) ?? [];
      arr.push(n.id);
      groups.set(n.category, arr);
    }
    for (const arr of groups.values()) {
      const center = arr[0];
      for (let i = 1; i < arr.length; i++) {
        out.push({ source: center, target: arr[i] });
      }
    }
    return out;
  });

  // ─── force simulation ─────────────────────────────────────────────────
  let sim: Simulation<Node, undefined> | null = null;
  let tick = $state(0);
  // svelte-ignore non_reactive_update
  let simNodes: Node[] = [];
  // svelte-ignore non_reactive_update
  let simLinks: Link[] = [];

  function buildSim() {
    if (sim) sim.stop();
    simNodes = nodes.map((n) => ({ ...n }));
    simLinks = links.map((l) => ({ ...l }));
    const cx = width / 2;
    const cy = height / 2;
    simNodes.forEach((n) => {
      n.x = cx + (Math.random() - 0.5) * width * 0.5;
      n.y = cy + (Math.random() - 0.5) * height * 0.5;
    });
    sim = forceSimulation<Node>(simNodes)
      .force('link', forceLink<Node, Link>(simLinks).id((d) => d.id).distance(38).strength(0.5))
      .force('charge', forceManyBody().strength(-55))
      .force('center', forceCenter(cx, cy).strength(0.06))
      .force('x', forceX(cx).strength(0.05))
      .force('y', forceY(cy).strength(0.10))
      .force('collide', forceCollide<Node>((d) => d.radius + 2))
      .on('tick', () => {
        const pad = 22;
        for (const n of simNodes) {
          if (n.x == null || n.y == null) continue;
          const r = n.radius + pad;
          if (n.x < r) { n.x = r; n.vx = 0; }
          else if (n.x > width - r) { n.x = width - r; n.vx = 0; }
          if (n.y < r) { n.y = r; n.vy = 0; }
          else if (n.y > height - r) { n.y = height - r; n.vy = 0; }
        }
        tick++;
      });
  }

  // ─── d3-zoom (휠 줌 + 배경 pan) ────────────────────────────────────────
  let transform = $state<ZoomTransform>(zoomIdentity);
  let svgEl: SVGSVGElement | null = null;

  function attachZoom(el: SVGSVGElement) {
    const z = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 4])
      .filter((event) => {
        // 노드 위 클릭은 d3-drag 가 처리 → zoom 무시. wheel 만 항상 허용.
        if (event.type === 'wheel') return true;
        const target = event.target as Element;
        return !target.closest('.node');
      })
      .on('zoom', (event) => {
        transform = event.transform;
      });
    select(el).call(z);
    return () => select(el).on('.zoom', null);
  }

  let detachZoom: (() => void) | null = null;

  // ─── d3-drag (노드 드래그) ────────────────────────────────────────────
  function attachDrag(g: SVGGElement, n: Node) {
    const d = drag<SVGGElement, Node>()
      .on('start', (event) => {
        if (!event.active && sim) sim.alphaTarget(0.3).restart();
        n.fx = n.x ?? null;
        n.fy = n.y ?? null;
      })
      .on('drag', (event) => {
        n.fx = event.x;
        n.fy = event.y;
      })
      .on('end', (event) => {
        if (!event.active && sim) sim.alphaTarget(0);
        n.fx = null;
        n.fy = null;
      });
    select(g).datum(n).call(d);
  }

  onMount(() => {
    buildSim();
    if (svgEl) detachZoom = attachZoom(svgEl);
  });
  onDestroy(() => {
    sim?.stop();
    detachZoom?.();
  });

  // 카테고리 centroid — cluster 라벨 위치.
  const centroids = $derived.by(() => {
    void tick;
    const m = new Map<string, { x: number; y: number; n: number }>();
    for (const n of simNodes) {
      if (n.x == null || n.y == null) continue;
      const prev = m.get(n.category) ?? { x: 0, y: 0, n: 0 };
      prev.x += n.x;
      prev.y += n.y;
      prev.n += 1;
      m.set(n.category, prev);
    }
    return m;
  });

  const tStr = $derived(`translate(${transform.x}, ${transform.y}) scale(${transform.k})`);
</script>

<svg
  bind:this={svgEl}
  viewBox="0 0 {width} {height}"
  class="graph"
  role="img"
  aria-label="마켓플레이스 관계성 그래프"
>
  <!-- 모든 그래프 컨텐츠는 zoom transform g 안에 -->
  <g class="zoom-wrap" transform={tStr}>
    <g class="nodes">
      {#key tick}
        {#each simNodes as n (n.id)}
          {#if n.x != null}
            {@const selected = n.svc.id === selectedId}
            <g
              class="node"
              class:selected
              transform="translate({n.x}, {n.y})"
              use:attachDrag={n}
              onclick={(e) => { e.stopPropagation(); onSelect?.(n.svc); }}
              role="presentation"
            >
              {#if selected}
                <circle r={n.radius + 6} fill="none" stroke={n.color} stroke-opacity="0.45" stroke-width="1" />
              {/if}
              <circle
                r={n.radius}
                fill={n.color}
                fill-opacity="0.92"
                stroke={selected ? '#f8fafc' : 'none'}
                stroke-width={selected ? 2 : 0}
              />
              {#if selected}
                <text class="sys-label" text-anchor="middle" y={-n.radius - 9}>{n.label}</text>
              {/if}
            </g>
          {/if}
        {/each}
      {/key}
    </g>

    <g class="cat-labels" pointer-events="none">
      {#key tick}
        {#each categories as cat (cat.key)}
          {@const c = centroids.get(cat.key)}
          {#if c && c.n > 0}
            <text
              x={c.x / c.n}
              y={c.y / c.n}
              class="cat-label"
              text-anchor="middle"
              fill={cat.color}
            >{cat.label} <tspan class="cat-count">· {cat.count}</tspan></text>
          {/if}
        {/each}
      {/key}
    </g>
  </g>
</svg>

<style>
  .graph {
    width: 100%;
    height: auto;
    display: block;
    cursor: grab;
    touch-action: none;
  }
  .graph:active { cursor: grabbing; }
  .node { cursor: pointer; }
  .cat-label {
    font-size: 13px;
    font-weight: 850;
    letter-spacing: -0.01em;
    paint-order: stroke;
    stroke: rgba(13, 17, 23, 0.92);
    stroke-width: 4;
    stroke-linejoin: round;
  }
  .cat-count {
    font-size: 11px;
    font-weight: 700;
    fill: rgba(248, 250, 252, 0.55);
  }
  .sys-label {
    fill: #f8fafc;
    font-size: 11px;
    font-weight: 700;
    paint-order: stroke;
    stroke: rgba(13, 17, 23, 0.92);
    stroke-width: 3.5;
    stroke-linejoin: round;
  }
</style>
