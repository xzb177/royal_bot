import os
import importlib
import logging

# 设置日志
logger = logging.getLogger(__name__)

# === 🛠️ 关键修复：加了 *args 来接收多余的参数 ===
def load(app, context, *args):
    """
    全自动插件加载器 (兼容旧版接口)
    自动扫描 features 目录下的所有 .py 文件并加载
    """
    logger.info("🔍 正在启动万能自动加载器...")
    
    # 定位 features 目录
    current_dir = os.path.dirname(__file__)
    features_dir = os.path.join(current_dir, 'features')
    
    if not os.path.exists(features_dir):
        logger.error(f"❌ 严重错误：找不到插件目录 {features_dir}")
        return

    # 获取所有 .py 文件并排序
    files = sorted([f for f in os.listdir(features_dir) if f.endswith(".py") and not f.startswith("_")])
    
    success_count = 0
    
    for filename in files:
        module_name = filename[:-3] # 去掉 .py
        full_module_name = f"royal_bot.features.{module_name}"
        
        try:
            # 尝试导入模块
            lib = importlib.import_module(full_module_name)
            
            # 尝试注册
            if hasattr(lib, "register"):
                lib.register(app, context)
                logger.info(f"✅ 加载成功: {module_name}")
                success_count += 1
            else:
                logger.warning(f"⚠️ 跳过 {module_name}: 未找到 register() 函数")
                
        except Exception as e:
            logger.error(f"❌ 加载失败 【{module_name}】: {e}")
            print(f"!!! 插件 {module_name} 加载出错: {e}")

    logger.info(f"🎉 所有插件处理完毕，共加载 {success_count} 个功能模块")

# === 接口兼容 ===
# 无论 bot.py 喊什么，都指向同一个函数
load_features = load
load_plugins = load
register_plugins = load
