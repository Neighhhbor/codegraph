import json

# 日志文件路径
LOG_FILE = "./missing_top5.log"

def is_parent_or_child(parent, child):
    """
    检查 parent 和 child 是否是父子路径关系。
    :param parent: 父路径 (例如 "mrjob.parse.is_s3_uri")
    :param child: 子路径 (例如 "mrjob.mrjob.parse.parse_s3_uri")
    :return: 是否是父子路径关系
    """
    parent_parts = parent.split(".")
    child_parts = child.split(".")

    # 父路径的字段数量不能多于子路径
    if len(parent_parts) > len(child_parts):
        return False

    # 检查每个字段是否是子字符串
    for parent_part, child_part in zip(parent_parts, child_parts):
        if parent_part not in child_part:
            return False

    # 检查最后一个字段是否完全一致
    return parent_parts[-1] == child_parts[len(parent_parts) - 1]


def filter_and_select_top5(data):
    """
    根据父子路径关系过滤检索结果，并保留前 5 条。
    :param data: 输入的测试数据
    :return: 处理后的数据
    """
    filtered_data = []

    with open(LOG_FILE, 'w', encoding='utf-8') as log:
        for item in data:
            namespace = item.get("namespace")  # 当前项的 namespace
            retrieved = item.get("retrieved", [])  # 检索结果

            filtered_retrieved = []
            for result in retrieved:
                similar_signature = result.get("similar_signature")  # 检索结果的 signature
                if not is_parent_or_child(namespace, similar_signature):  # 过滤掉父子路径
                    filtered_retrieved.append(result)

            # 按相似度排序并取前 5 条
            filtered_retrieved = sorted(
                filtered_retrieved, key=lambda x: x.get("similarity_score", 0), reverse=True
            )[:5]

            # 如果不足 5 条，记录日志
            if len(filtered_retrieved) < 5:
                log.write(
                    f"Namespace '{namespace}' only has {len(filtered_retrieved)} items after filtering.\n"
                )

            # 更新检索结果
            item["retrieved"] = filtered_retrieved
            filtered_data.append(item)

    return filtered_data


def main(input_file, output_file):
    """
    主函数：读取输入文件，处理数据并保存到输出文件。
    :param input_file: 输入文件路径
    :param output_file: 输出文件路径
    """
    # 加载 JSONL 文件
    with open(input_file, 'r', encoding='utf-8') as infile:
        data = [json.loads(line) for line in infile]

    # 处理数据
    filtered_data = filter_and_select_top5(data)

    # 保存处理后的数据
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for item in filtered_data:
            json.dump(item, outfile, ensure_ascii=False)
            outfile.write('\n')

    print(f"筛选并截取 Top-5 的数据已保存到文件：{output_file}")
    print(f"不足 5 条的记录已保存到日志：{LOG_FILE}")


if __name__ == "__main__":
    INPUT_FILE = "./top10_retrieved_rgrg.jsonl"  # 输入文件路径
    OUTPUT_FILE = "./top5_retrieved_filtered_rgrg.jsonl"  # 输出文件路径

    main(INPUT_FILE, OUTPUT_FILE)
