import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';

export default function RedCore({ status = 'IDLE' }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const w = el.clientWidth, h = el.clientHeight;

    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(40, w / h, 0.1, 100);
    cam.position.z = 5;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    const speed = status === 'THINKING' ? 0.025 : status === 'SPEAKING' ? 0.015 : 0.005;
    const coreColor = status === 'THINKING' ? 0xffb300 : status === 'SPEAKING' ? 0x00e676 : 0xe53e3e;

    // Inner core sphere
    const coreMat = new THREE.MeshBasicMaterial({ color: coreColor, transparent: true, opacity: 0.4 });
    const coreM = new THREE.Mesh(new THREE.SphereGeometry(0.35, 32, 32), coreMat);
    group.add(coreM);

    // Wireframe icosahedron
    const wireM = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.8, 1),
      new THREE.MeshBasicMaterial({ color: 0xe53e3e, wireframe: true, transparent: true, opacity: 0.5 })
    );
    group.add(wireM);

    // Concentric rings
    [1.1, 1.4, 1.7, 2.0].forEach((r, i) => {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(r, 0.008, 16, 100),
        new THREE.MeshBasicMaterial({ color: i % 2 === 0 ? 0xe53e3e : 0x00e5ff, transparent: true, opacity: 0.15 + i * 0.05 })
      );
      ring.rotation.x = Math.PI / 2 + (i * 0.15);
      ring.rotation.y = i * 0.3;
      group.add(ring);
    });

    // Radar sweep line
    const sweepGeo = new THREE.BufferGeometry();
    sweepGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0,0,0, 2,0,0]), 3));
    const sweepLine = new THREE.Line(sweepGeo, new THREE.LineBasicMaterial({ color: 0xe53e3e, transparent: true, opacity: 0.6 }));
    group.add(sweepLine);

    // Cross-hair lines
    const mkLine = (pts, color, op) => {
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pts), 3));
      const l = new THREE.Line(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity: op }));
      group.add(l);
    };
    mkLine([-2.2,0,0, 2.2,0,0], 0xe53e3e, 0.1);
    mkLine([0,-2.2,0, 0,2.2,0], 0xe53e3e, 0.1);

    // Particles
    const pCount = 80;
    const pPos = new Float32Array(pCount * 3);
    for (let i = 0; i < pCount * 3; i += 3) {
      const r = 1 + Math.random() * 2;
      const th = Math.random() * Math.PI * 2;
      pPos[i] = Math.cos(th) * r;
      pPos[i+1] = (Math.random() - 0.5) * 0.8;
      pPos[i+2] = Math.sin(th) * r;
    }
    const pGeo = new THREE.BufferGeometry(); pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
    group.add(new THREE.Points(pGeo, new THREE.PointsMaterial({ color: 0xe53e3e, size: 0.03, transparent: true, opacity: 0.6 })));

    // Small orbiting data nodes
    const nodes = [];
    for (let i = 0; i < 6; i++) {
      const n = new THREE.Mesh(
        new THREE.OctahedronGeometry(0.04),
        new THREE.MeshBasicMaterial({ color: i < 3 ? 0xe53e3e : 0x00e5ff })
      );
      nodes.push({ mesh: n, angle: (Math.PI * 2 / 6) * i, radius: 1.3 + (i % 2) * 0.4, speed: 0.01 + i * 0.003 });
      group.add(n);
    }

    let mx = 0, my = 0;
    const onMouse = (e) => { const r = el.getBoundingClientRect(); mx = ((e.clientX - r.left) / w - 0.5) * 0.4; my = ((e.clientY - r.top) / h - 0.5) * 0.4; };
    el.addEventListener('mousemove', onMouse);

    const clock = new THREE.Clock();
    let raf;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      wireM.rotation.y += speed;
      wireM.rotation.x += speed * 0.3;
      sweepLine.rotation.z = t * 0.8;

      const p = Math.sin(t * (status === 'THINKING' ? 6 : 2)) * 0.06 + 1;
      coreM.scale.setScalar(p);
      coreMat.opacity = 0.3 + Math.sin(t * 3) * 0.15;

      nodes.forEach(n => {
        n.angle += n.speed;
        n.mesh.position.x = Math.cos(n.angle) * n.radius;
        n.mesh.position.z = Math.sin(n.angle) * n.radius;
        n.mesh.position.y = Math.sin(t + n.angle) * 0.15;
      });

      group.rotation.y += (mx - group.rotation.y) * 0.03;
      group.rotation.x += (my * 0.5 - group.rotation.x) * 0.03;

      renderer.render(scene, cam);
    };
    animate();

    const onResize = () => { const nw = el.clientWidth, nh = el.clientHeight; cam.aspect = nw/nh; cam.updateProjectionMatrix(); renderer.setSize(nw, nh); };
    window.addEventListener('resize', onResize);

    return () => { cancelAnimationFrame(raf); el.removeEventListener('mousemove', onMouse); window.removeEventListener('resize', onResize); if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement); renderer.dispose(); };
  }, [status]);

  return <div ref={ref} className="w-full h-full cursor-crosshair" />;
}
