//
//  File.swift
//  Test
//
//  Created by woong on 5/19/25.
//

import SwiftUI

public protocol AProtocol: View {
    var a: Int { get set }
    var b: Bool { get }
}

public extension AProtocol {
    var b: Bool {
        false
    }
}
