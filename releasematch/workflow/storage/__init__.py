#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch 存储层包。

@package workflow.storage
@description
  抽象 Release 导航站线上数据的读写：
    - mysql_store: 本地 MySQL 测试（RM_STORAGE_BACKEND=mysql）
    - 后续 d1_store: 生产 D1 sync（RM_STORAGE_BACKEND=d1）
"""

from workflow.storage.mysql_store import MySQLStore

__all__ = ["MySQLStore"]
