//
//  Schedule.swift
//  ScheduleApp
//
//  スケジュールのデータモデル
//

import Foundation
import SwiftUI

/// スケジュールの優先度
enum Priority: String, Codable, CaseIterable {
    case low = "低"
    case medium = "中"
    case high = "高"

    var color: Color {
        switch self {
        case .low:
            return .green
        case .medium:
            return .orange
        case .high:
            return .red
        }
    }
}

/// スケジュールアイテム
struct Schedule: Identifiable, Codable {
    var id = UUID()
    var title: String
    var description: String
    var date: Date
    var startTime: Date
    var endTime: Date
    var priority: Priority
    var isCompleted: Bool
    var category: String
    var location: String

    init(
        id: UUID = UUID(),
        title: String = "",
        description: String = "",
        date: Date = Date(),
        startTime: Date = Date(),
        endTime: Date = Date().addingTimeInterval(3600),
        priority: Priority = .medium,
        isCompleted: Bool = false,
        category: String = "",
        location: String = ""
    ) {
        self.id = id
        self.title = title
        self.description = description
        self.date = date
        self.startTime = startTime
        self.endTime = endTime
        self.priority = priority
        self.isCompleted = isCompleted
        self.category = category
        self.location = location
    }

    /// 時間範囲を文字列で取得
    var timeRangeString: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        let start = formatter.string(from: startTime)
        let end = formatter.string(from: endTime)
        return "\(start) - \(end)"
    }

    /// 日付を文字列で取得
    var dateString: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.locale = Locale(identifier: "ja_JP")
        return formatter.string(from: date)
    }
}

/// サンプルデータ
extension Schedule {
    static var sampleData: [Schedule] {
        [
            Schedule(
                title: "チームミーティング",
                description: "週次の進捗確認ミーティング",
                date: Date(),
                startTime: Date(),
                endTime: Date().addingTimeInterval(3600),
                priority: .high,
                category: "仕事",
                location: "会議室A"
            ),
            Schedule(
                title: "歯医者の予約",
                description: "定期検診",
                date: Date().addingTimeInterval(86400),
                startTime: Date().addingTimeInterval(86400),
                endTime: Date().addingTimeInterval(90000),
                priority: .medium,
                category: "個人",
                location: "〇〇歯科医院"
            ),
            Schedule(
                title: "ジムトレーニング",
                description: "筋トレと有酸素運動",
                date: Date().addingTimeInterval(172800),
                startTime: Date().addingTimeInterval(172800),
                endTime: Date().addingTimeInterval(176400),
                priority: .low,
                category: "健康",
                location: "フィットネスジム"
            )
        ]
    }
}
