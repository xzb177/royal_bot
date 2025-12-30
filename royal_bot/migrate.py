import logging
import pkgutil
import importlib

logger = logging.getLogger(__name__)

def run_migrations(db, *args, **kwargs):
    """
    智能迁移脚本：尝试加载所有插件的数据库结构。
    如果某个插件报错，会自动跳过，保全大局。
    """
    logger.info(">>> 正在初始化数据库 (Smart Mode)...")

    try:
        # 尝试定位插件目录
        try:
            import royal_bot.plugins as plugin_package
        except ImportError:
            logger.warning("⚠️ 未找到插件目录，跳过数据库初始化")
            return

        path = plugin_package.__path__
        prefix = plugin_package.__name__ + "."

        # 遍历所有插件
        for _, name, _ in pkgutil.iter_modules(path, prefix):
            try:
                module = importlib.import_module(name)
                # 检查插件是否有建表函数 (ensure_schema)
                if hasattr(module, "ensure_schema"):
                    try:
                        # 尝试多种调用方式，总有一种能成功
                        try:
                            module.ensure_schema(db)
                        except TypeError:
                            # 如果参数不对，尝试不传参数调用
                            module.ensure_schema()
                        logger.info(f"✔ 数据库就绪: {name}")
                    except Exception as e:
                        logger.warning(f"⚠️ 插件 {name} 建表失败 (已跳过): {e}")
            except Exception as e:
                logger.warning(f"⚠️ 无法加载插件 {name}: {e}")

    except Exception as e:
        logger.error(f"❌ 迁移流程异常: {e}")

    logger.info(">>> 数据库检查完成")
