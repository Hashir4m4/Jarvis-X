import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';

export default function Jarvis3DCore({ status = 'IDLE' }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 300;
    const height = container.clientHeight || 300;

    // Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 5;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Group for entire core
    const coreGroup = new THREE.Group();
    scene.add(coreGroup);

    // Inner Core Icosahedron Wireframe
    const coreGeo = new THREE.IcosahedronGeometry(1.2, 2);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0x00f3ff,
      wireframe: true,
      transparent: true,
      opacity: 0.85
    });
    const innerMesh = new THREE.Mesh(coreGeo, coreMat);
    coreGroup.add(innerMesh);

    // Middle Solid Core with Glow
    const solidGeo = new THREE.SphereGeometry(0.7, 32, 32);
    const solidMat = new THREE.MeshBasicMaterial({
      color: status === 'THINKING' ? 0xff6b00 : (status === 'SPEAKING' ? 0x00ff9d : 0x00f3ff),
      transparent: true,
      opacity: 0.6
    });
    const solidMesh = new THREE.Mesh(solidGeo, solidMat);
    coreGroup.add(solidMesh);

    // Outer Orbital Ring 1
    const ringGeo1 = new THREE.TorusGeometry(1.9, 0.015, 16, 100);
    const ringMat1 = new THREE.MeshBasicMaterial({ color: 0x00f3ff, transparent: true, opacity: 0.7 });
    const ring1 = new THREE.Mesh(ringGeo1, ringMat1);
    ring1.rotation.x = Math.PI / 3;
    coreGroup.add(ring1);

    // Outer Orbital Ring 2
    const ringGeo2 = new THREE.TorusGeometry(2.3, 0.012, 16, 100);
    const ringMat2 = new THREE.MeshBasicMaterial({ color: 0x3b82f6, transparent: true, opacity: 0.5 });
    const ring2 = new THREE.Mesh(ringGeo2, ringMat2);
    ring2.rotation.y = Math.PI / 4;
    coreGroup.add(ring2);

    // Particle Swarm
    const particleCount = 200;
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
      positions[i] = (Math.random() - 0.5) * 6;
      positions[i + 1] = (Math.random() - 0.5) * 6;
      positions[i + 2] = (Math.random() - 0.5) * 6;
    }
    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const particleMat = new THREE.PointsMaterial({
      color: 0x00f3ff,
      size: 0.04,
      transparent: true,
      opacity: 0.75
    });
    const particleSystem = new THREE.Points(particleGeo, particleMat);
    coreGroup.add(particleSystem);

    // Mouse Interaction
    let mouseX = 0;
    let mouseY = 0;
    const handleMouseMove = (e) => {
      const rect = container.getBoundingClientRect();
      mouseX = ((e.clientX - rect.left) / width - 0.5) * 0.5;
      mouseY = ((e.clientY - rect.top) / height - 0.5) * 0.5;
    };
    container.addEventListener('mousemove', handleMouseMove);

    // Animation Loop
    let animationFrameId;
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      // Dynamic rotation speed based on state
      const rotSpeed = status === 'THINKING' ? 0.03 : (status === 'SPEAKING' ? 0.025 : 0.008);

      innerMesh.rotation.y += rotSpeed;
      innerMesh.rotation.x += rotSpeed * 0.5;

      ring1.rotation.z += rotSpeed * 1.2;
      ring2.rotation.z -= rotSpeed * 0.9;
      particleSystem.rotation.y -= rotSpeed * 0.3;

      // Pulse scaling
      const pulse = Math.sin(elapsedTime * (status === 'THINKING' ? 6 : 2)) * 0.08 + 1;
      innerMesh.scale.set(pulse, pulse, pulse);

      // Smooth camera motion towards mouse
      coreGroup.rotation.y += (mouseX - coreGroup.rotation.y) * 0.05;
      coreGroup.rotation.x += (mouseY - coreGroup.rotation.x) * 0.05;

      renderer.render(scene, camera);
    };

    animate();

    // Handle Resize
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      container.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [status]);

  return (
    <div 
      ref={mountRef} 
      className="w-full h-full min-h-[260px] relative flex items-center justify-center cursor-crosshair overflow-hidden"
    >
      <div className="absolute bottom-2 text-xs font-mono tracking-widest text-[#00f3ff] opacity-75 uppercase">
        AI CORE STATE: <span className="font-bold text-white">{status}</span>
      </div>
    </div>
  );
}
