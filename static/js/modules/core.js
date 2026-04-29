// 本文件负责前端模块基础命名空间，属于 static/js/modules 基础层；只提供轻量组合工具，不承载具体业务领域逻辑。
(function initInventoryModules(global) {
    const modules = global.InventoryModules || {};
    modules.features = modules.features || {};

    /**
     * 合并领域模块到 Alpine 状态对象。
     * @param {object} target 目标 Alpine 对象，必须是可变普通对象。
     * @param {object} feature 领域模块，支持 { state, methods } 或普通方法对象。
     * @returns {object} 返回合并后的 target，便于 app() 保持原入口。
     */
    modules.mergeFeature = function mergeFeature(target, feature) {
        if (!target || !feature) return target;
        const state = feature.state || {};
        const methods = feature.methods || feature;
        Object.assign(target, state, methods);
        return target;
    };

    /**
     * 创建统一的轻量 toast 描述对象。
     * @param {string} message 用户可见提示文案。
     * @param {string} type 提示类型，沿用现有 success/error/warning/info 语义。
     * @returns {{message: string, type: string}} 可交给现有 toast 渲染逻辑的描述。
     */
    modules.createToast = function createToast(message, type = 'info') {
        return {
            message: String(message || ''),
            type: type || 'info'
        };
    };

    /**
     * 登记延迟集成的领域模块，供最终集成任务统一挂载。
     * @param {string} name 模块名称，必须稳定且避免领域缩写。
     * @param {object} feature 可被 mergeFeature 合并的 { state, methods } 描述。
     * @returns {object} 返回已登记的 feature，便于链式测试或调试。
     */
    modules.registerFeature = function registerFeature(name, feature) {
        if (!name || !feature) return feature;
        modules.features[name] = feature;
        return feature;
    };

    global.InventoryModules = modules;
})(window);
