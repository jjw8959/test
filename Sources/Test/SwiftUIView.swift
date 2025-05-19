//
//  SwiftUIView.swift
//  Test
//
//  Created by woong on 5/19/25.
//

import SwiftUI

struct SwiftUIView: AProtocol {
    
    var a: Int = 1
    
    var body: some View {
        Text(/*@START_MENU_TOKEN@*/"Hello, World!"/*@END_MENU_TOKEN@*/)
            .padding()
        Text("\(a)")
    }
}

#Preview {
    SwiftUIView()
}
