<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import uPlot from 'uplot';
  import 'uplot/dist/uPlot.min.css';

  let {
    data,
    options,
    onclickx
  }: {
    data: uPlot.AlignedData;
    options: Omit<uPlot.Options, 'width' | 'height'>;
    onclickx?: (xValue: number) => void;
  } = $props();

  let container: HTMLDivElement;
  let chart: uPlot | null = null;
  let resizeObserver: ResizeObserver | null = null;

  function build() {
    chart?.destroy();
    const width = container.clientWidth || 600;
    const full: uPlot.Options = { ...options, width, height: 260 } as uPlot.Options;
    if (onclickx) {
      full.hooks = {
        ...full.hooks,
        ready: [
          (u) => {
            u.over.addEventListener('click', () => {
              const idx = u.cursor.idx;
              if (idx != null && u.data[0][idx] != null) onclickx(u.data[0][idx] as number);
            });
          }
        ]
      };
    }
    chart = new uPlot(full, data, container);
  }

  onMount(() => {
    build();
    resizeObserver = new ResizeObserver(() => {
      if (chart && container.clientWidth && chart.width !== container.clientWidth) {
        chart.setSize({ width: container.clientWidth, height: 260 });
      }
    });
    resizeObserver.observe(container);
  });

  $effect(() => {
    if (chart) chart.setData(data);
  });

  onDestroy(() => {
    resizeObserver?.disconnect();
    chart?.destroy();
  });
</script>

<div bind:this={container}></div>
