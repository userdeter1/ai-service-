import { Controller, Get, Post, Body, Query, UseGuards, Request } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { AuthGuard } from '../../guards/auth.guard';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';

@ApiTags('AI')
@Controller('ai')
export class AiController {
    constructor(private prisma: PrismaService) { }

    @Get('slot-availability')
    @ApiOperation({ summary: 'Get AI recommended slot availability' })
    async getAvailability() {
        // Simple proxy to get slots for the demo
        const slots = await this.prisma.timeSlot.findMany({
            include: { gate: true }
        });

        return {
            status: 'success',
            data: slots.map(s => ({
                slotId: s.id,
                startTime: s.startTime,
                endTime: s.endTime,
                capacity: s.maxCapacity,
                current: s.currentBookings,
                status: s.currentBookings < s.maxCapacity ? 'AVAILABLE' : 'FULL',
                gate: s.gate.name,
                gateId: s.gateId,
                port: 'Rotterdam World Gateway'
            }))
        };
    }

    @Post('chat')
    @ApiBearerAuth()
    @UseGuards(AuthGuard)
    @ApiOperation({ summary: 'Chat with AI assistant' })
    async chat(@Request() req, @Body() body: any) {
        // Mocking AI response for the demo if AI service is not reachable
        // In a real scenario, this would fetch from AI_SERVICE_URL
        return {
            message: `Hello ${req.user.name}, I see you're asking about "${body.message}". How can I help with your booking?`,
            intent: "GENERAL_QUERY",
            conversationId: body.conversation_id || "demo-conv-123"
        };
    }
}
