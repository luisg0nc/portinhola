<script lang="ts">
  let { size = 28 }: { size?: number } = $props();
</script>

<!-- Portinhola: the little arched door. -->
<svg
  width={size}
  height={size}
  viewBox="0 0 512 512"
  aria-hidden="true"
  focusable="false"
>
  <rect width="512" height="512" rx="116" fill="#c2542e" />
  <path d="M176 416 V256 a80 80 0 0 1 160 0 V416 Z" fill="#faf6f0" />
  <circle cx="304" cy="332" r="15" fill="#d97706" />
</svg>
