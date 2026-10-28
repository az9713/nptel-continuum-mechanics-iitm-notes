/* Prescribed kinematics only. No network, storage, or external dependencies. */
(() => {
  'use strict';
  const shear = document.getElementById('lab-shear');
  const angle = document.getElementById('lab-angle');
  if (!shear || !angle) return;
  const render = () => {
    const g = Number(shear.value), degrees = Number(angle.value);
    const theta = degrees * Math.PI / 180;
    const c = Math.cos(theta), s = Math.sin(theta);
    const f = [[c, c*g - s], [s, s*g + c]];
    const points = [[-0.5,-0.5],[0.5,-0.5],[0.5,0.5],[-0.5,0.5]];
    const mapped = points.map(([x,y]) => {
      const a = f[0][0]*x + f[0][1]*y;
      const b = f[1][0]*x + f[1][1]*y;
      return `${300+100*a},${220-100*b}`;
    });
    document.getElementById('lab-polygon').setAttribute('points', mapped.join(' '));
    document.getElementById('lab-shear-value').textContent = g.toFixed(2);
    document.getElementById('lab-angle-value').textContent = `${degrees}°`;
    const e12 = g/2, e22 = g*g/2;
    const small11 = c-1, small22 = s*g+c-1;
    const small12 = (c*g-s+s)/2;
    const error = Math.sqrt(small11*small11 + 2*(small12-e12)**2 + (small22-e22)**2);
    document.getElementById('lab-metrics').textContent =
      `J = 1.0000; exact E₁₁ = 0, E₁₂ = ${e12.toFixed(4)}, E₂₂ = ${e22.toFixed(4)}. ` +
      `Linearized ε₁₁ = ${small11.toFixed(4)}, ε₁₂ = ${small12.toFixed(4)}, ε₂₂ = ${small22.toFixed(4)}. ` +
      `Frobenius difference = ${error.toFixed(4)}.`;
  };
  shear.addEventListener('input', render);
  angle.addEventListener('input', render);
  render();
})();
