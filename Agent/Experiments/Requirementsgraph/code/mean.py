import json
from tqdm import tqdm

INPUT_FILE = "./final_data_v2.jsonl"  # 输入文件路径

def calculate_overall_mean(input_file):
    """
    计算整个 JSONL 文件的依赖均值。
    :param input_file: 输入文件路径
    :return: 包含总体均值的字典
    """
    total_child_count = 0
    total_context_count = 0
    total_similarity_count = 0
    total_items = 0

    with open(input_file, "r", encoding="utf-8") as infile:
        for line in tqdm(infile, desc="Calculating overall dependency means"):
            data = json.loads(line.strip())
            dependency = data.get("dependency", {})

            # 累计各依赖的数量
            total_child_count += len(dependency.get("child_requirement", []))
            total_context_count += len(dependency.get("context_requirement", []))
            total_similarity_count += len(dependency.get("similarity_requirement", []))
            total_items += 1

    if total_items == 0:
        raise ValueError("The input file is empty or no valid data found.")

    # 计算总体均值
    overall_means = {
        "child_requirement_mean": total_child_count / total_items,
        "context_requirement_mean": total_context_count / total_items,
        "similarity_requirement_mean": total_similarity_count / total_items,
        "total_mean": (total_child_count + total_context_count + total_similarity_count) / total_items
    }

    return overall_means


def main():
    """
    主函数：计算总体均值并打印。
    """
    overall_means = calculate_overall_mean(INPUT_FILE)

    print("Overall Dependency Means:")
    print(json.dumps(overall_means, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
