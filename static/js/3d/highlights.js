// 本文件负责 3D 场景高亮动画：BOM 高亮、LED 脉冲、相机飞入和领料序号标签。
(function registerHighlights(global) {
    'use strict';

    var modules = global.InventoryModules || (global.InventoryModules = {});
    modules._3D = modules._3D || {};

    var HIGHLIGHT_COLOR = 0x1f7a6c;
    var LED_PULSE_COLOR = 0x1f7a6c;
    var PULSE_SPEED = 3.0;
    var state = {
        pulsePhase: 0,
        highlightedBoxes: [],
        ledPulseBoxId: null,
        ledPulseExpiresAt: 0,
        flyTarget: null,
        flyLookAt: null,
        flyDone: null,
        isFlying: false
    };

    /** 查找收纳盒所在抽屉；柜内盒需要通过 drawerMap 定位，独立盒走 standaloneBoxMap。 */
    function findDrawerByBoxId(sm, boxId) {
        var keys;
        var i;
        var drawer;

        if (!sm || !boxId) return null;
        keys = Object.keys(sm.drawerMap || {});
        for (i = 0; i < keys.length; i += 1) {
            drawer = sm.drawerMap[keys[i]];
            if (drawer && Number(drawer.userData.boxId) === Number(boxId)) {
                return drawer;
            }
        }
        return null;
    }

    /** 抽屉面板是第一个把手拾取面，也就是 BoxGeometry Mesh；这里用位置靠前的面板优先。 */
    function findDrawerPanel(sm, boxId) {
        var drawer = findDrawerByBoxId(sm, boxId);
        var fallback = null;
        var i;
        var child;

        if (!drawer) return null;
        for (i = 0; i < drawer.children.length; i += 1) {
            child = drawer.children[i];
            if (!child.isMesh || !child.material) continue;
            if (child.userData && child.userData.type === 'handle' && child.geometry && child.geometry.type === 'BoxGeometry') {
                return child;
            }
            if (!fallback && child.geometry && child.geometry.type === 'BoxGeometry') {
                fallback = child;
            }
        }
        return fallback;
    }

    function findStandaloneBox(sm, boxId) {
        return sm && sm.standaloneBoxMap ? sm.standaloneBoxMap[boxId] || sm.standaloneBoxMap[String(boxId)] || null : null;
    }

    /** 对材质发光做可恢复设置，避免清除高亮时破坏将来可能存在的模型自带 emissive。 */
    function setMaterialGlow(material, color, intensity, source) {
        if (!material || !material.emissive) return;
        material.userData = material.userData || {};
        if (!material.userData._highlightBase) {
            material.userData._highlightBase = {
                color: material.emissive.getHex(),
                intensity: Number(material.emissiveIntensity || 0)
            };
        }
        material.userData._highlightSource = source || 'highlight';
        material.emissive.setHex(color);
        material.emissiveIntensity = intensity;
    }

    function restoreMaterialGlow(material, source) {
        var base;
        if (!material || !material.emissive || !material.userData || !material.userData._highlightBase) return;
        if (source && material.userData._highlightSource && material.userData._highlightSource !== source) return;

        base = material.userData._highlightBase;
        material.emissive.setHex(base.color || 0x000000);
        material.emissiveIntensity = Number(base.intensity || 0);
        delete material.userData._highlightBase;
        delete material.userData._highlightSource;
    }

    function applyGlowToObject(object, color, intensity, source) {
        if (!object) return;
        object.traverse(function glow(child) {
            if (child.isMesh && child.material) {
                setMaterialGlow(child.material, color, intensity, source);
            }
        });
    }

    function restoreGlowOnObject(object, source) {
        if (!object) return;
        object.traverse(function restore(child) {
            if (child.isMesh && child.material) {
                restoreMaterialGlow(child.material, source);
            }
        });
    }

    /** BOM 高亮：柜内盒高亮抽屉面板，独立盒高亮整个盒体。 */
    function highlightDrawers(sm, boxIds) {
        var normalized = uniqueIds(boxIds);

        clearHighlights(sm);
        state.highlightedBoxes = normalized;

        normalized.forEach(function highlightBox(boxId) {
            var panel = findDrawerPanel(sm, boxId);
            var standalone = findStandaloneBox(sm, boxId);

            if (panel) {
                setMaterialGlow(panel.material, HIGHLIGHT_COLOR, 0.35, 'bom');
            }
            if (standalone) {
                applyGlowToObject(standalone, HIGHLIGHT_COLOR, 0.3, 'bom');
            }
        });
    }

    /** 清除 BOM 高亮，不影响正在运行的 LED 脉冲。 */
    function clearHighlights(sm) {
        if (!sm) return;

        state.highlightedBoxes.forEach(function clearBox(boxId) {
            var panel = findDrawerPanel(sm, boxId);
            var standalone = findStandaloneBox(sm, boxId);

            if (panel) restoreMaterialGlow(panel.material, 'bom');
            if (standalone) restoreGlowOnObject(standalone, 'bom');
        });
        state.highlightedBoxes = [];
    }

    /** 启动 3D LED 脉冲；durationMs 结束后自动恢复原高亮状态。 */
    function startPulse(boxId, durationMs) {
        state.ledPulseBoxId = Number(boxId || 0) || null;
        state.ledPulseExpiresAt = durationMs ? Date.now() + Number(durationMs) : Date.now() + 5000;
        state.pulsePhase = 0;
    }

    function stopPulse(sm) {
        var boxId = state.ledPulseBoxId;
        var panel;
        var standalone;

        state.ledPulseBoxId = null;
        state.ledPulseExpiresAt = 0;
        if (!sm || !boxId) return;

        panel = findDrawerPanel(sm, boxId);
        standalone = findStandaloneBox(sm, boxId);
        if (panel) restoreMaterialGlow(panel.material, 'led');
        if (standalone) restoreGlowOnObject(standalone, 'led');

        if (state.highlightedBoxes.indexOf(Number(boxId)) !== -1) {
            highlightDrawers(sm, state.highlightedBoxes);
        }
    }

    /** 每帧更新 LED 正弦脉冲。 */
    function updatePulse(sm, deltaTime) {
        var intensity;
        var panel;
        var standalone;

        if (!state.ledPulseBoxId || !sm) return;
        if (state.ledPulseExpiresAt && Date.now() > state.ledPulseExpiresAt) {
            stopPulse(sm);
            return;
        }

        state.pulsePhase += (deltaTime || 0.016) * PULSE_SPEED;
        intensity = 0.25 + 0.55 * Math.abs(Math.sin(state.pulsePhase));
        panel = findDrawerPanel(sm, state.ledPulseBoxId);
        standalone = findStandaloneBox(sm, state.ledPulseBoxId);

        if (panel) setMaterialGlow(panel.material, LED_PULSE_COLOR, intensity, 'led');
        if (standalone) applyGlowToObject(standalone, LED_PULSE_COLOR, intensity, 'led');
    }

    function flyToTarget(sm, targetPos, lookAtPos, done) {
        if (!sm || !targetPos || !lookAtPos) return;
        state.flyTarget = targetPos.clone();
        state.flyLookAt = lookAtPos.clone();
        state.flyDone = typeof done === 'function' ? done : null;
        state.isFlying = true;
    }

    /** 每帧更新相机飞入；到达后执行一次回调，例如自动打开抽屉。 */
    function updateFly(sm) {
        var target;
        var lookAt;
        var done;

        if (!state.isFlying || !sm || !sm.camera || !sm.controls) return false;

        target = state.flyTarget;
        lookAt = state.flyLookAt;
        sm.camera.position.lerp(target, 0.08);
        sm.controls.target.lerp(lookAt, 0.08);
        sm.controls.update();

        if (sm.camera.position.distanceTo(target) < 0.08 && sm.controls.target.distanceTo(lookAt) < 0.08) {
            sm.camera.position.copy(target);
            sm.controls.target.copy(lookAt);
            sm.controls.update();
            state.isFlying = false;
            done = state.flyDone;
            state.flyDone = null;
            if (done) done();
            return false;
        }
        return true;
    }

    /** 飞入到收纳盒位置；柜内盒飞到抽屉前方并在完成后打开抽屉。 */
    function flyToBox(sm, boxId, openDrawerCallback) {
        var THREE = global.THREE;
        var drawer = findDrawerByBoxId(sm, boxId);
        var targetWorld = new THREE.Vector3();
        var lookAt;
        var cameraPos;
        var standalone;
        var constants = modules._3D || {};

        if (!sm || !THREE || !boxId) return false;

        if (drawer) {
            drawer.getWorldPosition(targetWorld);
            lookAt = targetWorld.clone();
            lookAt.y += (constants.LAYER_HEIGHT || 0.35) * 0.5;
            cameraPos = targetWorld.clone();
            cameraPos.y += 2.2;
            cameraPos.z += 3.2;
            flyToTarget(sm, cameraPos, lookAt, function openAfterFly() {
                if (openDrawerCallback) openDrawerCallback(drawer);
            });
            return true;
        }

        standalone = findStandaloneBox(sm, boxId);
        if (standalone) {
            standalone.getWorldPosition(targetWorld);
            lookAt = targetWorld.clone();
            lookAt.y += 0.15;
            cameraPos = targetWorld.clone();
            cameraPos.y += 1.8;
            cameraPos.z += 2.6;
            flyToTarget(sm, cameraPos, lookAt);
            return true;
        }

        return false;
    }

    /** 更新 3D 领料序号标签，和 2D pickLabels 共用同一份 boxId->序号映射。 */
    function updatePickLabels(sm, boxIdOrderMap) {
        var map = boxIdOrderMap || {};
        if (!sm) return;

        clearPickLabels(sm);
        Object.keys(map).forEach(function addPick(boxIdKey) {
            var drawer = findDrawerByBoxId(sm, boxIdKey);
            var standalone = findStandaloneBox(sm, boxIdKey);
            var order = map[boxIdKey];
            var label;

            if (!order) return;
            if (drawer) {
                label = createPickLabel(order);
                label.position.set(0, (modules._3D.LAYER_HEIGHT || 0.35) * 0.32, (modules._3D.CABINET_DEPTH || 0.8) / 2 + 0.055);
                drawer.add(label);
            } else if (standalone) {
                label = createPickLabel(order);
                label.position.set(0, 0.24, 0.24);
                standalone.add(label);
            }
        });
    }

    function clearPickLabels(sm) {
        Object.keys((sm && sm.drawerMap) || {}).forEach(function clearDrawer(key) {
            removePickLabelsFrom(sm.drawerMap[key]);
        });
        Object.keys((sm && sm.standaloneBoxMap) || {}).forEach(function clearBox(key) {
            removePickLabelsFrom(sm.standaloneBoxMap[key]);
        });
    }

    function removePickLabelsFrom(parent) {
        var toRemove = [];
        if (!parent || !parent.children) return;
        parent.children.forEach(function collect(child) {
            if (child.userData && child.userData.type === 'label-pick') {
                toRemove.push(child);
            }
        });
        toRemove.forEach(function remove(child) {
            parent.remove(child);
            if (modules._3D.disposeLabelElement) {
                modules._3D.disposeLabelElement(child);
            } else if (child.element && child.element.parentNode) {
                child.element.parentNode.removeChild(child.element);
            }
        });
    }

    function createPickLabel(order) {
        var CSS2DObject = global.CSS2DObjectModule || (global.THREE && global.THREE.CSS2DObject);
        var div = global.document.createElement('div');
        var label;

        if (!CSS2DObject) throw new Error('CSS2DObject 未加载，无法创建领料序号标签。');
        div.className = 'pick-label-3d';
        div.textContent = String(order);
        label = new CSS2DObject(div);
        label.userData = { type: 'label-pick', order: order };
        return label;
    }

    function uniqueIds(ids) {
        var seen = {};
        var result = [];
        (ids || []).forEach(function add(id) {
            var numeric = Number(id || 0);
            if (!numeric || seen[numeric]) return;
            seen[numeric] = true;
            result.push(numeric);
        });
        return result;
    }

    modules._3D.findDrawerByBoxId = findDrawerByBoxId;
    modules._3D.findDrawerPanel = findDrawerPanel;
    modules._3D.highlightDrawers = highlightDrawers;
    modules._3D.clearHighlights = clearHighlights;
    modules._3D.startPulse = startPulse;
    modules._3D.stopPulse = stopPulse;
    modules._3D.updatePulse = updatePulse;
    modules._3D.flyToTarget = flyToTarget;
    modules._3D.updateFly = updateFly;
    modules._3D.flyToBox = flyToBox;
    modules._3D.updatePickLabels = updatePickLabels;
    modules._3D.clearPickLabels = clearPickLabels;
    modules._3D._highlightState = state;
})(window);
