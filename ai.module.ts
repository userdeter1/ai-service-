import { Module } from '@nestjs/common';
import { AiController } from './ai.controller';
import { PrismaModule } from '../prisma/prisma.module';

@Module({
    imports: [PrismaModule],
    controllers: [AiController],
    providers: [],
    exports: [],
})
export class AiModule { }
