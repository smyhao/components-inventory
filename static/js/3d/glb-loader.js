// 本文件提供轻量 GLB 2.0 加载能力，只覆盖模型库 MVP 需要的未压缩 mesh、材质和节点锚点。
(function registerGlbLoader(global) {
    'use strict';

    var modules = global.InventoryModules || (global.InventoryModules = {});
    modules._3D = modules._3D || {};

    var COMPONENT_ARRAYS = {
        5120: Int8Array,
        5121: Uint8Array,
        5122: Int16Array,
        5123: Uint16Array,
        5125: Uint32Array,
        5126: Float32Array
    };
    var COMPONENT_SIZES = {
        5120: 1,
        5121: 1,
        5122: 2,
        5123: 2,
        5125: 4,
        5126: 4
    };
    var TYPE_SIZES = {
        SCALAR: 1,
        VEC2: 2,
        VEC3: 3,
        VEC4: 4,
        MAT4: 16
    };
    var cache = {};

    function normalizeNodeName(name) {
        return String(name || '').replace(/\s+/g, '').toUpperCase().replace(/[-_.]\d+$/, '');
    }

    async function loadGlb(url) {
        var response;
        var buffer;

        if (!url) throw new Error('GLB 地址为空');
        if (cache[url]) return cloneLoaded(cache[url]);

        response = await fetch(url);
        if (!response.ok) throw new Error('GLB 加载失败 HTTP ' + response.status);
        buffer = await response.arrayBuffer();
        cache[url] = parseGlb(buffer);
        return cloneLoaded(cache[url]);
    }

    function cloneLoaded(loaded) {
        return {
            scene: loaded.scene.clone(true),
            source: loaded
        };
    }

    function parseGlb(buffer) {
        var view = new DataView(buffer);
        var totalLength;
        var offset = 12;
        var json = null;
        var bin = null;

        if (buffer.byteLength < 20 || magic(buffer) !== 'glTF') throw new Error('不是有效 GLB 文件');
        if (view.getUint32(4, true) !== 2) throw new Error('仅支持 GLB 2.0');
        totalLength = view.getUint32(8, true);
        if (totalLength !== buffer.byteLength) throw new Error('GLB 文件长度不匹配');

        while (offset + 8 <= buffer.byteLength) {
            var chunkLength = view.getUint32(offset, true);
            var chunkType = text(buffer, offset + 4, 4);
            offset += 8;
            if (chunkType === 'JSON') {
                json = JSON.parse(text(buffer, offset, chunkLength).replace(/[\s\0]+$/g, ''));
            } else if (chunkType === 'BIN\0') {
                bin = buffer.slice(offset, offset + chunkLength);
            }
            offset += chunkLength;
        }

        if (!json) throw new Error('GLB 缺少 JSON chunk');
        return buildScene(json, bin || new ArrayBuffer(0));
    }

    function magic(buffer) {
        return text(buffer, 0, 4);
    }

    function text(buffer, offset, length) {
        return new TextDecoder('utf-8').decode(new Uint8Array(buffer, offset, length));
    }

    function buildScene(gltf, bin) {
        var THREE = global.THREE;
        var scene = new THREE.Group();
        var nodes = gltf.nodes || [];
        var sceneIndex = Number(gltf.scene || 0);
        var gltfScene = (gltf.scenes || [])[sceneIndex] || (gltf.scenes || [])[0] || {};

        (gltfScene.nodes || []).forEach(function addRootNode(index) {
            if (nodes[index]) scene.add(buildNode(gltf, bin, index));
        });
        scene.userData.anchorMap = collectAnchors(scene);
        return { scene: scene, gltf: gltf };
    }

    function buildNode(gltf, bin, index) {
        var THREE = global.THREE;
        var node = gltf.nodes[index] || {};
        var object = node.mesh !== undefined ? buildMesh(gltf, bin, node.mesh) : new THREE.Group();
        var normalized = normalizeNodeName(node.name);

        object.name = node.name || '';
        object.userData.normalizedName = normalized;
        if (normalized.indexOf('_ANCHOR') > -1) {
            object.visible = false;
            object.userData.isAnchor = true;
        }
        applyTransform(object, node);
        (node.children || []).forEach(function addChild(childIndex) {
            if ((gltf.nodes || [])[childIndex]) object.add(buildNode(gltf, bin, childIndex));
        });
        return object;
    }

    function applyTransform(object, node) {
        if (node.matrix && node.matrix.length === 16) {
            object.matrix.fromArray(node.matrix);
            object.matrix.decompose(object.position, object.quaternion, object.scale);
            return;
        }
        if (node.translation) object.position.fromArray(node.translation);
        if (node.rotation) object.quaternion.fromArray(node.rotation);
        if (node.scale) object.scale.fromArray(node.scale);
    }

    function buildMesh(gltf, bin, meshIndex) {
        var THREE = global.THREE;
        var meshDef = (gltf.meshes || [])[meshIndex] || {};
        var group = new THREE.Group();
        (meshDef.primitives || []).forEach(function addPrimitive(primitive) {
            var geometry = buildGeometry(gltf, bin, primitive);
            var material = buildMaterial(gltf, primitive.material);
            var mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            group.add(mesh);
        });
        return group;
    }

    function buildGeometry(gltf, bin, primitive) {
        var THREE = global.THREE;
        var geometry = new THREE.BufferGeometry();
        var attributes = primitive.attributes || {};

        addAttribute(gltf, bin, geometry, attributes.POSITION, 'position');
        addAttribute(gltf, bin, geometry, attributes.NORMAL, 'normal');
        addAttribute(gltf, bin, geometry, attributes.TEXCOORD_0, 'uv');
        if (primitive.indices !== undefined) {
            geometry.setIndex(new THREE.BufferAttribute(readAccessor(gltf, bin, primitive.indices), 1));
        }
        if (!geometry.getAttribute('normal')) {
            geometry.computeVertexNormals();
        }
        geometry.computeBoundingBox();
        geometry.computeBoundingSphere();
        return geometry;
    }

    function addAttribute(gltf, bin, geometry, accessorIndex, name) {
        if (accessorIndex === undefined) return;
        var accessor = (gltf.accessors || [])[accessorIndex];
        geometry.setAttribute(name, new global.THREE.BufferAttribute(readAccessor(gltf, bin, accessorIndex), TYPE_SIZES[accessor.type] || 3));
    }

    function readAccessor(gltf, bin, accessorIndex) {
        var accessor = (gltf.accessors || [])[accessorIndex];
        var bufferView = (gltf.bufferViews || [])[accessor.bufferView];
        var ArrayType = COMPONENT_ARRAYS[accessor.componentType];
        var componentSize = COMPONENT_SIZES[accessor.componentType];
        var itemSize = TYPE_SIZES[accessor.type] || 1;
        var byteOffset = (bufferView.byteOffset || 0) + (accessor.byteOffset || 0);
        var stride = bufferView.byteStride || itemSize * componentSize;
        var length = accessor.count * itemSize;
        var i;
        var c;
        var source;
        var result;

        if (!ArrayType || !bufferView) throw new Error('不支持的 GLB accessor');
        if (stride === itemSize * componentSize) {
            return new ArrayType(bin, byteOffset, length);
        }

        // SolidWorks 等工具偶尔会写入交错 buffer；复制成紧凑数组后 Three.js 才能稳定消费。
        source = new DataView(bin, bufferView.byteOffset || 0, bufferView.byteLength || 0);
        result = new ArrayType(length);
        for (i = 0; i < accessor.count; i += 1) {
            for (c = 0; c < itemSize; c += 1) {
                result[i * itemSize + c] = readComponent(source, (accessor.byteOffset || 0) + i * stride + c * componentSize, accessor.componentType);
            }
        }
        return result;
    }

    function readComponent(view, offset, componentType) {
        if (componentType === 5120) return view.getInt8(offset);
        if (componentType === 5121) return view.getUint8(offset);
        if (componentType === 5122) return view.getInt16(offset, true);
        if (componentType === 5123) return view.getUint16(offset, true);
        if (componentType === 5125) return view.getUint32(offset, true);
        if (componentType === 5126) return view.getFloat32(offset, true);
        return 0;
    }

    function buildMaterial(gltf, materialIndex) {
        var THREE = global.THREE;
        var materialDef = (gltf.materials || [])[materialIndex] || {};
        var pbr = materialDef.pbrMetallicRoughness || {};
        var base = pbr.baseColorFactor || [0.78, 0.76, 0.72, 1];
        var roughness = pbr.roughnessFactor === undefined ? 0.55 : pbr.roughnessFactor;
        var metalness = pbr.metallicFactor === undefined ? 0.08 : pbr.metallicFactor;

        if (metalness > 0.75) {
            // SolidWorks 会把“黄铜/金属外观”导出为全金属材质；网页场景没有 HDR 环境反射时会发黑。
            // 模型库更看重 CAD 外观色的可辨识度，因此在这里按展示材质降金属度。
            metalness = 0.28;
            roughness = Math.max(roughness, 0.34);
        }

        return new THREE.MeshStandardMaterial({
            name: materialDef.name || '',
            color: new THREE.Color(base[0], base[1], base[2]),
            opacity: base[3] === undefined ? 1 : base[3],
            transparent: base[3] !== undefined && base[3] < 1,
            roughness: roughness,
            metalness: metalness,
            side: materialDef.doubleSided ? THREE.DoubleSide : THREE.FrontSide
        });
    }

    function collectAnchors(root) {
        var anchors = {};
        root.updateMatrixWorld(true);
        root.traverse(function collect(object) {
            var normalized = object.userData && object.userData.normalizedName;
            if (!normalized || normalized.indexOf('_ANCHOR') === -1) return;
            anchors[normalized] = object;
        });
        return anchors;
    }

    function findNode(root, normalizedName) {
        var found = null;
        root.traverse(function visit(object) {
            if (!found && object.userData && object.userData.normalizedName === normalizedName) {
                found = object;
            }
        });
        return found;
    }

    function markSubtree(object, data) {
        if (!object) return;
        object.traverse(function mark(child) {
            child.userData = Object.assign({}, child.userData || {}, data);
        });
    }

    function scaleToDimensions(object, widthMm, heightMm, depthMm) {
        var THREE = global.THREE;
        var box;
        var size;
        var sx;
        var sy;
        var sz;

        if (!object) return;
        object.updateMatrixWorld(true);
        box = getRenderableBox(object);
        if (box.isEmpty()) return;
        size = new THREE.Vector3();
        box.getSize(size);
        sx = widthMm && size.x > 0 ? (widthMm * 0.001) / size.x : 1;
        sy = heightMm && size.y > 0 ? (heightMm * 0.001) / size.y : 1;
        sz = depthMm && size.z > 0 ? (depthMm * 0.001) / size.z : 1;
        object.scale.multiply(new THREE.Vector3(sx, sy, sz));
    }

    function normalizeToBaseCenter(object) {
        var THREE = global.THREE;
        var box;
        var center;

        if (!object) return;
        object.updateMatrixWorld(true);
        box = getRenderableBox(object);
        if (box.isEmpty()) return;
        center = new THREE.Vector3();
        box.getCenter(center);
        // 真实 GLB 经常保留 CAD 装配坐标；入库后只负责外观，所以渲染时把外观盒子归一到本地原点。
        object.position.x -= center.x;
        object.position.y -= box.min.y;
        object.position.z -= center.z;
    }

    function alignToGround(object) {
        var box;

        if (!object) return;
        object.updateMatrixWorld(true);
        box = getRenderableBox(object);
        if (box.isEmpty()) return;
        // 多个 GLB 部件叠加后再做一次整体验底，避免 CAD 原点或锚点偏移让最终模型悬空。
        object.position.y -= box.min.y;
    }

    function getRenderableBox(object) {
        var THREE = global.THREE;
        var box = new THREE.Box3();
        var childBox = new THREE.Box3();
        var hasMesh = false;

        if (!object) return box;
        object.updateMatrixWorld(true);
        object.traverse(function expand(child) {
            var normalized = child.userData && child.userData.normalizedName;
            if (!child.geometry || child.userData && child.userData.isAnchor) return;
            if (normalized && normalized.indexOf('_ANCHOR') !== -1) return;
            if (!child.geometry.boundingBox) child.geometry.computeBoundingBox();
            childBox.copy(child.geometry.boundingBox).applyMatrix4(child.matrixWorld);
            box.union(childBox);
            hasMesh = true;
        });
        if (!hasMesh) {
            return new THREE.Box3().setFromObject(object);
        }
        return box;
    }

    modules._3DModels = {
        loadGlb: loadGlb,
        normalizeNodeName: normalizeNodeName,
        findNode: findNode,
        markSubtree: markSubtree,
        scaleToDimensions: scaleToDimensions,
        normalizeToBaseCenter: normalizeToBaseCenter,
        alignToGround: alignToGround,
        getRenderableBox: getRenderableBox
    };
})(window);
