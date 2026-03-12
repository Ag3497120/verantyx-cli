//
//  ScheduleViewModel.swift
//  ScheduleApp
//
//  スケジュール管理のViewModel
//

import Foundation
import SwiftUI

class ScheduleViewModel: ObservableObject {
    @Published var schedules: [Schedule] = []
    @Published var selectedDate: Date = Date()
    @Published var searchText: String = ""

    private let saveKey = "SavedSchedules"

    init() {
        loadSchedules()
    }

    /// フィルタリングされたスケジュール
    var filteredSchedules: [Schedule] {
        let dateFiltered = schedules.filter { schedule in
            Calendar.current.isDate(schedule.date, inSameDayAs: selectedDate)
        }

        if searchText.isEmpty {
            return dateFiltered.sorted { $0.startTime < $1.startTime }
        } else {
            return dateFiltered.filter { schedule in
                schedule.title.localizedCaseInsensitiveContains(searchText) ||
                schedule.description.localizedCaseInsensitiveContains(searchText) ||
                schedule.category.localizedCaseInsensitiveContains(searchText)
            }.sorted { $0.startTime < $1.startTime }
        }
    }

    /// カテゴリ一覧
    var categories: [String] {
        Array(Set(schedules.map { $0.category })).sorted()
    }

    /// スケジュールを追加
    func addSchedule(_ schedule: Schedule) {
        schedules.append(schedule)
        saveSchedules()
    }

    /// スケジュールを更新
    func updateSchedule(_ schedule: Schedule) {
        if let index = schedules.firstIndex(where: { $0.id == schedule.id }) {
            schedules[index] = schedule
            saveSchedules()
        }
    }

    /// スケジュールを削除
    func deleteSchedule(_ schedule: Schedule) {
        schedules.removeAll { $0.id == schedule.id }
        saveSchedules()
    }

    /// スケジュールを削除（IndexSet版）
    func deleteSchedules(at offsets: IndexSet) {
        let schedulesToDelete = offsets.map { filteredSchedules[$0] }
        schedules.removeAll { schedule in
            schedulesToDelete.contains(where: { $0.id == schedule.id })
        }
        saveSchedules()
    }

    /// 完了状態をトグル
    func toggleCompletion(_ schedule: Schedule) {
        if let index = schedules.firstIndex(where: { $0.id == schedule.id }) {
            schedules[index].isCompleted.toggle()
            saveSchedules()
        }
    }

    /// スケジュールを保存
    private func saveSchedules() {
        if let encoded = try? JSONEncoder().encode(schedules) {
            UserDefaults.standard.set(encoded, forKey: saveKey)
        }
    }

    /// スケジュールを読み込み
    private func loadSchedules() {
        if let data = UserDefaults.standard.data(forKey: saveKey),
           let decoded = try? JSONDecoder().decode([Schedule].self, from: data) {
            schedules = decoded
        } else {
            // 初回起動時はサンプルデータを使用
            schedules = Schedule.sampleData
            saveSchedules()
        }
    }

    /// 指定日にスケジュールがあるか
    func hasSchedule(on date: Date) -> Bool {
        schedules.contains { schedule in
            Calendar.current.isDate(schedule.date, inSameDayAs: date)
        }
    }

    /// 指定日のスケジュール数
    func scheduleCount(on date: Date) -> Int {
        schedules.filter { schedule in
            Calendar.current.isDate(schedule.date, inSameDayAs: date)
        }.count
    }
}
