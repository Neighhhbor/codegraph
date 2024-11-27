import json
from tqdm import tqdm

INPUT_FILE = "./top10_retrieved_filtered.jsonl"  # 过滤后的输入文件路径
OUTPUT_FILE = "./top5_retrieved.jsonl"  # 输出文件路径
LOG_FILE = "./missing_top5.log"  # 日志文件路径


def process_top5(data, log_file):
    """
    从每条数据的 `retrieved` 字段中取前 5 条。
    如果不足 5 条，记录日志。
    :param data: 输入数据
    :param log_file: 日志文件路径
    :return: 处理后的数据
    """
    processed_data = []

    with open(log_file, 'w', encoding='utf-8') as log:
        for item in data:
            retrieved = item.get("retrieved", [])

            # 如果不足 5 条，记录日志
            if len(retrieved) < 5:
                log.write(
                    f"Namespace '{item['namespace']}' only has {len(retrieved)} items after filtering.\n"
                )

            # 截取前 5 条
            item["retrieved"] = retrieved[:5]
            processed_data.append(item)

    return processed_data


def main():
    """
    主函数：读取过滤后的数据，从 `retrieved` 字段中保留前 5 条。
    如果不足 5 条，记录日志。
    """
    # 加载 JSONL 文件
    with open(INPUT_FILE, 'r', encoding='utf-8') as infile:
        data = [json.loads(line) for line in infile]

    # 处理数据
    processed_data = process_top5(data, LOG_FILE)

    # 保存处理后的数据
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        for item in processed_data:
            json.dump(item, outfile, ensure_ascii=False)
            outfile.write('\n')

    print(f"处理完成，结果保存到：{OUTPUT_FILE}")
    print(f"不足 5 条的数据记录在：{LOG_FILE}")


if __name__ == "__main__":
    main()
